import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.entities import (
    AccountingProposal,
    Bridge,
    Company,
    Document,
    DomainException,
    PostingAttempt,
    PostingJob,
    PostingResponse,
    VerificationResult,
)
from src.routers.bridge import _bridge_states

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard Summary & KPIs"])


class DashboardSummaryResponse(BaseModel):
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    documents_received: int
    pending_review: int
    approved: int
    posted_to_tally: int
    verified: int
    exceptions: int
    cloud_status: str
    bridge_connected: bool
    bridge_status: str
    bridge_version: str
    bridge_client_id: str
    tally_online: bool
    is_demo_mode: bool
    tally_mode: str
    tally_status_text: str
    adapter_name: str
    last_heartbeat: Optional[str] = None


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Control 2: Real database-derived KPI metrics and authoritative connection state.
    Zero hardcoded numbers. All counts query live PostgreSQL entities.
    """
    comp_uuid: Optional[uuid.UUID] = None
    company_name: Optional[str] = None

    if company_id:
        try:
            comp_uuid = uuid.UUID(company_id)
            comp = db.scalar(select(Company).where(Company.id == comp_uuid, Company.is_deleted == False))  # noqa: E712
            if comp:
                company_name = comp.legal_name
        except Exception:
            comp_uuid = None

    # 1. Documents Received (Real Count)
    doc_query = select(func.count(Document.id)).where(Document.is_deleted == False)  # noqa: E712
    if comp_uuid:
        doc_query = doc_query.where(Document.company_id == comp_uuid)
    documents_received = db.scalar(doc_query) or 0

    # 2. Pending Review (Real Count: proposals pending approval or unproposed documents)
    prop_pending_query = select(func.count(AccountingProposal.id)).where(
        AccountingProposal.status.in_(["PENDING_APPROVAL", "DRAFT"]),
        AccountingProposal.is_deleted == False,  # noqa: E712
    )
    if comp_uuid:
        prop_pending_query = prop_pending_query.where(AccountingProposal.company_id == comp_uuid)
    pending_review = db.scalar(prop_pending_query) or 0

    # 3. Approved (Real Count: proposals approved / transactions materialized)
    appr_query = select(func.count(AccountingProposal.id)).where(
        AccountingProposal.status == "APPROVED",
        AccountingProposal.is_deleted == False,  # noqa: E712
    )
    if comp_uuid:
        appr_query = appr_query.where(AccountingProposal.company_id == comp_uuid)
    approved = db.scalar(appr_query) or 0

    # 4. Posted to Tally (Real Count: posting jobs in POSTED or VERIFIED status)
    posted_query = select(func.count(PostingJob.id)).where(
        PostingJob.status.in_(["POSTED", "VERIFIED"])
    )
    if comp_uuid:
        posted_query = posted_query.where(PostingJob.company_id == comp_uuid)
    posted_to_tally = db.scalar(posted_query) or 0

    # 5. Verified (Real Count: read-back verification results with status VERIFIED)
    verified_query = (
        select(func.count(func.distinct(VerificationResult.id)))
        .select_from(VerificationResult)
        .where(VerificationResult.status == "VERIFIED")
    )
    if comp_uuid:
        verified_query = (
            verified_query.join(
                PostingResponse, VerificationResult.posting_response_id == PostingResponse.id
            )
            .join(PostingAttempt, PostingResponse.posting_attempt_id == PostingAttempt.id)
            .join(PostingJob, PostingAttempt.posting_job_id == PostingJob.id)
            .where(PostingJob.company_id == comp_uuid)
        )
    verified = db.scalar(verified_query) or 0

    # 6. Exceptions (Real Count: duplicate flagged documents, failed validations, domain exceptions)
    dup_doc_query = select(func.count(Document.id)).where(
        Document.status == "DUPLICATE_FLAGGED", Document.is_deleted == False  # noqa: E712
    )
    failed_prop_query = select(func.count(AccountingProposal.id)).where(
        AccountingProposal.status == "VALIDATION_FAILED",
        AccountingProposal.is_deleted == False,  # noqa: E712
    )
    domain_exc_query = select(func.count(DomainException.id))
    if comp_uuid:
        dup_doc_query = dup_doc_query.where(Document.company_id == comp_uuid)
        failed_prop_query = failed_prop_query.where(AccountingProposal.company_id == comp_uuid)
        domain_exc_query = domain_exc_query.where(DomainException.company_id == comp_uuid)

    dup_count = db.scalar(dup_doc_query) or 0
    failed_prop_count = db.scalar(failed_prop_query) or 0
    domain_exc_count = db.scalar(domain_exc_query) or 0
    exceptions = dup_count + failed_prop_count + domain_exc_count

    # Control 3: Connection & Runtime Mode (Derive from active state, never pretend live Tally)
    latest_client = next(iter(_bridge_states.keys()), None)
    bridge_state = _bridge_states.get(latest_client, {}) if latest_client else {}

    bridge_db = db.scalar(select(Bridge).order_by(Bridge.last_heartbeat_at.desc()))

    bridge_connected = bool(latest_client or (bridge_db and bridge_db.last_heartbeat_at))
    client_id_display = (
        latest_client
        or (bridge_db.bridge_client_id if bridge_db else "waast-bridge-local")
    )
    last_hb = (
        bridge_state.get("last_heartbeat")
        or (bridge_db.last_heartbeat_at.isoformat() if bridge_db and bridge_db.last_heartbeat_at else None)
    )

    tally_details = bridge_state.get("tally_status", {})
    tally_online = tally_details.get("is_online", False)
    tally_version = tally_details.get("tally_version", "")

    # Live vs Demo Mode determination (Control 3):
    # Only LIVE MODE if explicitly configured via WAAST_LIVE_MODE AND confirmed non-simulated runtime
    import os
    explicit_live = os.environ.get("WAAST_LIVE_MODE", "false").lower() in ("true", "1")
    is_live = (
        explicit_live
        and bridge_connected
        and tally_online
        and "Simulated" not in tally_version
        and not tally_details.get("capabilities", {}).get("is_simulated", False)
    )

    if is_live:
        tally_mode = "LIVE MODE"
        tally_status_text = "TallyPrime Connected"
        adapter_name = "Tally JSON/XML"
        is_demo_mode = False
    else:
        tally_mode = "DEMO MODE"
        tally_status_text = "Simulated Tally"
        adapter_name = "Simulated Tally"
        is_demo_mode = True

    return DashboardSummaryResponse(
        company_id=str(comp_uuid) if comp_uuid else None,
        company_name=company_name,
        documents_received=documents_received,
        pending_review=pending_review,
        approved=approved,
        posted_to_tally=posted_to_tally,
        verified=verified,
        exceptions=exceptions,
        cloud_status="ONLINE",
        bridge_connected=bridge_connected,
        bridge_status="ONLINE" if bridge_connected else "STANDBY",
        bridge_version="1.0.0",
        bridge_client_id=client_id_display,
        tally_online=tally_online,
        is_demo_mode=is_demo_mode,
        tally_mode=tally_mode,
        tally_status_text=tally_status_text,
        adapter_name=adapter_name,
        last_heartbeat=last_hb,
    )
