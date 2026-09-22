import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ai.models import ExtractedInvoiceData
from src.core.database import get_db
from src.models.entities import (
    AccountingProposal,
    Approval,
    AuditEvent,
    Bridge,
    Company,
    Document,
    Ledger,
    PostingJob,
    Transaction,
    TransactionLine,
    User,
)
from src.routers.bridge import _pending_job_queue
from src.services.proposal_engine import ProposalEngine

router = APIRouter(prefix="/api/v1/proposals", tags=["Human Approval & Posting Job Creation"])


# =========================================================================
# SCHEMAS
# =========================================================================


class ApprovalRequest(BaseModel):
    decision: str = "APPROVED"  # APPROVED, REJECTED, MODIFIED_AND_APPROVED
    comments: Optional[str] = None
    user_id: Optional[str] = None
    approval_signature: Optional[str] = None
    authority_context: Optional[str] = "PRIMARY_APPROVER"


class ApprovalResponse(BaseModel):
    approval_id: str
    proposal_id: str
    decision: str
    decision_timestamp: str
    status: str
    comments: Optional[str] = None
    authority_context: Optional[str] = None
    transaction_id: Optional[str] = None
    posting_job_id: Optional[str] = None
    document_status: Optional[str] = None


class AuditEventResponse(BaseModel):
    id: str
    action: str
    actor_type: str
    actor_id: str
    entity_type: str
    entity_id: str
    changes: Optional[dict[str, Any]] = None
    event_metadata: Optional[dict[str, Any]] = None
    recorded_at: str


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.post(
    "/{proposal_id}/approve",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
)
def approve_proposal(
    proposal_id: str,
    payload: Optional[ApprovalRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Phase 3G & 3H: Authoritative Human Approval & Posting Job creation.
    1. Records immutable Approval record with user decision and context.
    2. Materializes immutable authoritative Transaction and TransactionLine records.
    3. Queues a PostingJob for Bridge pickup and adds it to the bridge polling queue.
    4. Advances Document state: PENDING_APPROVAL -> APPROVED.
    5. Records append-only AuditEvent.
    """
    if payload is None:
        payload = ApprovalRequest()

    prop_uuid = uuid.UUID(proposal_id)
    proposal = db.scalar(
        select(AccountingProposal).where(
            AccountingProposal.id == prop_uuid,
            AccountingProposal.is_deleted == False,  # noqa: E712
        )
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="Accounting proposal not found")

    if proposal.status == "APPROVED":
        raise HTTPException(status_code=400, detail="Proposal is already approved")
    if proposal.status == "REJECTED":
        raise HTTPException(status_code=400, detail="Proposal has been rejected")

    # Ensure a valid User exists for foreign key constraint
    user = None
    if payload.user_id:
        try:
            user = db.scalar(select(User).where(User.id == uuid.UUID(payload.user_id)))
        except Exception:
            pass

    if not user:
        user = db.scalar(select(User).where(User.email == "approver@waast360.local"))
        if not user:
            user = User(
                organization_id=proposal.organization_id,
                email="approver@waast360.local",
                full_name="Primary Finance Approver",
                hashed_password="local-dev-mock-hash",
                is_active=True,
            )
            db.add(user)
            db.flush()

    # 1. Record Approval
    approval_sig = payload.approval_signature or f"SIG-{uuid.uuid4().hex[:8].upper()}"
    approval = Approval(
        accounting_proposal_id=proposal.id,
        user_id=user.id,
        decision=payload.decision,
        approval_step=1,
        authority_context=payload.authority_context or "PRIMARY_APPROVER",
        comments=payload.comments or "Approved via WAAST360 Lite Golden Path",
        approval_signature=approval_sig,
    )
    db.add(approval)
    db.flush()

    # Lookup associated document
    doc = db.scalar(select(Document).where(Document.id == proposal.document_id))
    company = db.scalar(select(Company).where(Company.id == proposal.company_id))

    if payload.decision == "REJECTED":
        proposal.status = "REJECTED"
        if doc:
            doc.status = "REJECTED"
        # Audit event
        db.add(
            AuditEvent(
                organization_id=proposal.organization_id,
                company_id=proposal.company_id,
                actor_type="USER",
                actor_id=str(user.id),
                action="PROPOSAL_REJECTED",
                entity_type="AccountingProposal",
                entity_id=proposal.id,
                changes={"status": "REJECTED", "comments": payload.comments},
            )
        )
        db.commit()
        return ApprovalResponse(
            approval_id=str(approval.id),
            proposal_id=str(proposal.id),
            decision="REJECTED",
            decision_timestamp=approval.decision_timestamp.isoformat(),
            status="REJECTED",
            comments=payload.comments,
            authority_context=approval.authority_context,
            document_status="REJECTED",
        )

    # 2. Materialize Authoritative Transaction
    ref_no = (
        doc.document_number
        if doc and doc.document_number
        else f"TXN-{uuid.uuid4().hex[:8].upper()}"
    )
    transaction = Transaction(
        organization_id=proposal.organization_id,
        company_id=proposal.company_id,
        accounting_proposal_id=proposal.id,
        voucher_type=proposal.voucher_type,
        voucher_date=proposal.proposed_date,
        reference_number=ref_no,
        total_amount=proposal.total_amount,
        narration=proposal.narration,
    )
    db.add(transaction)
    db.flush()

    # 3. Create Transaction Lines with Ledgers
    # Extract lines deterministically from extraction or fallback
    extracted_data = None
    if doc and doc.versions and doc.versions[0].extractions:
        extraction = doc.versions[0].extractions[0]
        if extraction.raw_response_json:
            try:
                extracted_data = ExtractedInvoiceData.model_validate(extraction.raw_response_json)
            except Exception:
                pass

    proposed_lines = []
    if extracted_data:
        proposed_lines, _, _ = ProposalEngine.generate_proposal(extracted_data)

    line_dicts_for_bridge = []
    if proposed_lines:
        for idx, line in enumerate(proposed_lines, start=1):
            # Find or create Ledger in company
            ledger = db.scalar(
                select(Ledger).where(
                    Ledger.company_id == proposal.company_id,
                    Ledger.name == line.ledger_name,
                    Ledger.is_deleted == False,  # noqa: E712
                )
            )
            if not ledger:
                parent_group = (
                    "Sundry Creditors"
                    if not line.is_debit
                    else ("Duties & Taxes" if "GST" in line.ledger_name else "Purchase Accounts")
                )
                ledger = Ledger(
                    organization_id=proposal.organization_id,
                    company_id=proposal.company_id,
                    name=line.ledger_name,
                    parent_group=parent_group,
                    opening_balance=0.0,
                )
                db.add(ledger)
                db.flush()

            t_line = TransactionLine(
                transaction_id=transaction.id,
                line_number=idx,
                ledger_id=ledger.id,
                is_debit=line.is_debit,
                amount=line.amount,
            )
            db.add(t_line)
            line_dicts_for_bridge.append(
                {
                    "ledger_name": line.ledger_name,
                    "amount": float(line.amount),
                    "is_debit": line.is_debit,
                }
            )
    else:
        # Fallback double-entry line
        default_ledger = db.scalar(
            select(Ledger).where(
                Ledger.company_id == proposal.company_id,
                Ledger.name == "Purchase A/c",
                Ledger.is_deleted == False,  # noqa: E712
            )
        )
        if not default_ledger:
            default_ledger = Ledger(
                organization_id=proposal.organization_id,
                company_id=proposal.company_id,
                name="Purchase A/c",
                parent_group="Purchase Accounts",
                opening_balance=0.0,
            )
            db.add(default_ledger)
            db.flush()
        t_line = TransactionLine(
            transaction_id=transaction.id,
            line_number=1,
            ledger_id=default_ledger.id,
            is_debit=True,
            amount=proposal.total_amount,
        )
        db.add(t_line)
        line_dicts_for_bridge.append(
            {
                "ledger_name": "Purchase A/c",
                "amount": float(proposal.total_amount),
                "is_debit": True,
            }
        )

    # 4. Find or Create Bridge Record
    bridge = db.scalar(select(Bridge).where(Bridge.organization_id == proposal.organization_id))
    if not bridge:
        bridge = Bridge(
            organization_id=proposal.organization_id,
            bridge_client_id="waast-bridge-local",
            api_key_hash="dev-key",
            status="ONLINE",
        )
        db.add(bridge)
        db.flush()

    # 5. Create PostingJob
    posting_job = PostingJob(
        organization_id=proposal.organization_id,
        company_id=proposal.company_id,
        transaction_id=transaction.id,
        bridge_id=bridge.id,
        status="QUEUED",
        scheduled_at=datetime.now(timezone.utc),
    )
    db.add(posting_job)
    db.flush()

    # 6. Enqueue into Bridge Polling Queue
    company_name = company.trade_name or company.legal_name if company else "Tata Motors Limited"
    correlation_id = f"CORR-{posting_job.id.hex[:12].upper()}"
    job_payload = {
        "job_id": str(posting_job.id),
        "correlation_id": correlation_id,
        "job_type": "POSTING",
        "payload": {
            "company_ref": {
                "company_name": company_name,
                "guid": str(company.id) if company else None,
                "tally_company_id": None,
            },
            "voucher_type": proposal.voucher_type,
            "voucher_date": proposal.proposed_date.isoformat(),
            "reference_number": ref_no,
            "narration": proposal.narration,
            "lines": line_dicts_for_bridge,
        },
    }
    _pending_job_queue.append(job_payload)

    # 7. Advance Statuses
    proposal.status = "APPROVED"
    if doc:
        doc.status = "APPROVED"

    # 8. Record Immutable Audit Event
    audit = AuditEvent(
        organization_id=proposal.organization_id,
        company_id=proposal.company_id,
        actor_type="USER",
        actor_id=str(user.id),
        action="PROPOSAL_APPROVED",
        entity_type="AccountingProposal",
        entity_id=proposal.id,
        changes={"status": "APPROVED", "decision": payload.decision},
        event_metadata={
            "transaction_id": str(transaction.id),
            "posting_job_id": str(posting_job.id),
            "reference_number": ref_no,
            "correlation_id": correlation_id,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(approval)

    return ApprovalResponse(
        approval_id=str(approval.id),
        proposal_id=str(proposal.id),
        decision=approval.decision,
        decision_timestamp=approval.decision_timestamp.isoformat(),
        status="APPROVED",
        comments=approval.comments,
        authority_context=approval.authority_context,
        transaction_id=str(transaction.id),
        posting_job_id=str(posting_job.id),
        document_status=doc.status if doc else "APPROVED",
    )


@router.post(
    "/{proposal_id}/reject",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
)
def reject_proposal(
    proposal_id: str,
    payload: Optional[ApprovalRequest] = None,
    db: Session = Depends(get_db),
):
    """Convenience endpoint to reject an accounting proposal."""
    if payload is None:
        payload = ApprovalRequest(decision="REJECTED")
    else:
        payload.decision = "REJECTED"
    return approve_proposal(proposal_id=proposal_id, payload=payload, db=db)
