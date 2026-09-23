import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ai.models import ExtractedInvoiceData
from src.core.database import get_db
from src.models.entities import (
    AccountingProposal,
    Document,
    Ledger,
    PostingJob,
    Transaction,
    ValidationResult,
)
from src.services.proposal_engine import ProposalEngine

router = APIRouter(prefix="/api/v1/proposals", tags=["Accounting Proposals & Validation"])


# =========================================================================
# SCHEMAS
# =========================================================================


class ProposalLineResponse(BaseModel):
    ledger_name: str
    amount: float
    is_debit: bool


class ValidationCheckResponse(BaseModel):
    rule_code: str
    severity: str
    is_passed: bool
    message: str


class AccountingProposalResponse(BaseModel):
    id: str
    document_id: str
    voucher_type: str
    proposed_date: str
    total_amount: float
    tax_amount: float
    narration: Optional[str] = None
    status: str
    lines: list[ProposalLineResponse]
    validations: list[ValidationCheckResponse]
    transaction_id: Optional[str] = None
    posting_job_id: Optional[str] = None
    posting_status: Optional[str] = None
    tally_voucher_number: Optional[str] = None
    tally_guid: Optional[str] = None
    actual_amount: Optional[float] = None
    expected_amount: Optional[float] = None
    verification_status: Optional[str] = None
    verified_at: Optional[str] = None


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.post(
    "/generate/{document_id}",
    response_model=AccountingProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_proposal(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Phases 3D, 3E, 3F:
    Generate structured double-entry accounting proposal from extracted invoice.
    Applies deterministic rules validation and duplicate detection.
    """
    doc_uuid = uuid.UUID(document_id)
    doc = db.scalar(select(Document).where(Document.id == doc_uuid, Document.is_deleted == False))  # noqa: E712
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    version = doc.versions[0] if doc.versions else None
    if not version or not version.extractions:
        raise HTTPException(status_code=400, detail="Document has no AI extraction")

    extraction = version.extractions[0]
    extracted_data = ExtractedInvoiceData.model_validate(extraction.raw_response_json)

    # Fetch existing invoice references for duplicate check
    existing_proposals = db.scalars(
        select(AccountingProposal).where(
            AccountingProposal.company_id == doc.company_id,
            AccountingProposal.is_deleted == False,  # noqa: E712
        )
    ).all()
    existing_invoices = [p.narration for p in existing_proposals if p.narration]

    # Run Proposal & Validation Engine
    lines, validation_results, is_all_passed = ProposalEngine.generate_proposal(
        extracted=extracted_data,
        existing_invoices=existing_invoices,
    )

    # Parse proposed date
    try:
        prop_date = date.fromisoformat(extracted_data.invoice_date[:10])
    except Exception:
        prop_date = date.today()

    narration = f"Purchase from {extracted_data.vendor_name} vide Inv #{extracted_data.invoice_number} dtd {extracted_data.invoice_date}"

    # Determine status
    has_blocker = any(not r.is_passed and r.severity == "BLOCKER" for r in validation_results)
    proposal_status = "VALIDATION_FAILED" if has_blocker else "PENDING_APPROVAL"

    proposal = AccountingProposal(
        organization_id=doc.organization_id,
        company_id=doc.company_id,
        document_id=doc.id,
        document_extraction_id=extraction.id,
        voucher_type="Purchase",
        proposed_date=prop_date,
        total_amount=extracted_data.total_amount,
        tax_amount=extracted_data.cgst_amount
        + extracted_data.sgst_amount
        + extracted_data.igst_amount,
        narration=narration,
        status=proposal_status,
    )
    db.add(proposal)
    db.flush()

    # Persist ValidationResult records
    validation_records = []
    for vr in validation_results:
        rec = ValidationResult(
            accounting_proposal_id=proposal.id,
            rule_code=vr.rule_code,
            severity=vr.severity,
            is_passed=vr.is_passed,
            message=vr.message,
            details=vr.details,
        )
        db.add(rec)
        validation_records.append(
            ValidationCheckResponse(
                rule_code=vr.rule_code,
                severity=vr.severity,
                is_passed=vr.is_passed,
                message=vr.message,
            )
        )

    # Progress Document stage
    doc.status = "PROPOSED"
    db.commit()
    db.refresh(proposal)

    return AccountingProposalResponse(
        id=str(proposal.id),
        document_id=str(proposal.document_id),
        voucher_type=proposal.voucher_type,
        proposed_date=proposal.proposed_date.isoformat(),
        total_amount=float(proposal.total_amount),
        tax_amount=float(proposal.tax_amount),
        narration=proposal.narration,
        status=proposal.status,
        lines=[
            ProposalLineResponse(
                ledger_name=line.ledger_name,
                amount=line.amount,
                is_debit=line.is_debit,
            )
            for line in lines
        ],
        validations=validation_records,
    )


@router.get("", response_model=List[AccountingProposalResponse])
def list_proposals(
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List accounting proposals with current review status and persisted verification details."""
    query = (
        select(AccountingProposal)
        .where(AccountingProposal.is_deleted == False)  # noqa: E712
        .order_by(AccountingProposal.created_at.desc())
    )
    if company_id:
        query = query.where(AccountingProposal.company_id == uuid.UUID(company_id))

    props = db.scalars(query).all()
    results = []
    for p in props:
        validations = [
            ValidationCheckResponse(
                rule_code=v.rule_code,
                severity=v.severity,
                is_passed=v.is_passed,
                message=v.message,
            )
            for v in p.validations
        ]

        # 1. Resolve lines: from TransactionLine if approved, else from DocumentExtraction
        lines: list[ProposalLineResponse] = []
        txn = db.scalar(
            select(Transaction).where(Transaction.accounting_proposal_id == p.id)
        )
        if txn and txn.lines:
            for line in txn.lines:
                ledger = db.scalar(select(Ledger).where(Ledger.id == line.ledger_id))
                ledger_name = ledger.name if ledger else "Purchase A/c"
                lines.append(
                    ProposalLineResponse(
                        ledger_name=ledger_name,
                        amount=float(line.amount),
                        is_debit=line.is_debit,
                    )
                )
        elif p.document_extraction and p.document_extraction.raw_response_json:
            try:
                ext_data = ExtractedInvoiceData.model_validate(p.document_extraction.raw_response_json)
                gen_lines, _, _ = ProposalEngine.generate_proposal(ext_data)
                lines = [
                    ProposalLineResponse(
                        ledger_name=gl.ledger_name,
                        amount=gl.amount,
                        is_debit=gl.is_debit,
                    )
                    for gl in gen_lines
                ]
            except Exception:
                pass

        # 2. Resolve PostingJob & Verification details
        posting_job_id = None
        posting_status = None
        tally_vch_no = None
        tally_guid = None
        act_amount = None
        exp_amount = None
        verif_status = None
        verif_at = None

        if txn:
            pjob = db.scalar(
                select(PostingJob)
                .where(PostingJob.transaction_id == txn.id)
                .order_by(PostingJob.created_at.desc())
            )
            if pjob:
                posting_job_id = str(pjob.id)
                posting_status = pjob.status
                if pjob.attempts:
                    for att in pjob.attempts:
                        for resp in att.responses:
                            if resp.tally_voucher_number:
                                tally_vch_no = resp.tally_voucher_number
                            if resp.tally_voucher_guid:
                                tally_guid = resp.tally_voucher_guid
                            for vr in resp.verifications:
                                verif_status = vr.status
                                if vr.actual_amount is not None:
                                    act_amount = float(vr.actual_amount)
                                if vr.expected_amount is not None:
                                    exp_amount = float(vr.expected_amount)
                                if vr.verified_at:
                                    verif_at = vr.verified_at.isoformat()
                                if vr.actual_tally_voucher_number:
                                    tally_vch_no = vr.actual_tally_voucher_number
                                if vr.tally_guid:
                                    tally_guid = vr.tally_guid

        results.append(
            AccountingProposalResponse(
                id=str(p.id),
                document_id=str(p.document_id),
                voucher_type=p.voucher_type,
                proposed_date=p.proposed_date.isoformat(),
                total_amount=float(p.total_amount),
                tax_amount=float(p.tax_amount),
                narration=p.narration,
                status=p.status,
                lines=lines,
                validations=validations,
                transaction_id=str(txn.id) if txn else None,
                posting_job_id=posting_job_id,
                posting_status=posting_status,
                tally_voucher_number=tally_vch_no,
                tally_guid=tally_guid,
                actual_amount=act_amount,
                expected_amount=exp_amount,
                verification_status=verif_status,
                verified_at=verif_at,
            )
        )
    return results
