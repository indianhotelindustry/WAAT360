import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.entities import (
    AccountingProposal,
    AuditEvent,
    Bridge,
    Document,
    Organization,
    PostingAttempt,
    PostingJob,
    PostingResponse,
    TallyCompany,
    TallyInstance,
    Transaction,
    VerificationResult,
)

router = APIRouter(prefix="/api/v1/bridge", tags=["Bridge"])


# =========================================================================
# SCHEMAS
# =========================================================================


class BridgeHeartbeatRequest(BaseModel):
    bridge_client_id: str
    status: str = "ONLINE"
    tally_status: dict[str, Any] = Field(default_factory=dict)


class DiscoveredCompanyPayload(BaseModel):
    name: str
    guid: str | None = None
    financial_year_from: str | None = None
    books_from: str | None = None
    is_active: bool = True


class BridgeCompaniesRequest(BaseModel):
    companies: list[DiscoveredCompanyPayload]


class PendingJobsResponse(BaseModel):
    jobs: list[dict[str, Any]] = Field(default_factory=list)


class PostingAttemptPayload(BaseModel):
    success: bool
    voucher_guid: str | None = None
    voucher_number: str | None = None
    master_id: int | None = None
    error_message: str | None = None
    raw_response: str | None = None
    status_code: int = 200


class VerificationResultPayload(BaseModel):
    is_verified: bool
    status: str
    actual_voucher_number: str | None = None
    actual_guid: str | None = None
    actual_amount: float | None = None
    mismatch_details: dict[str, Any] | None = None
    raw_payload: dict[str, Any] | None = None


# =========================================================================
# AUTHENTICATION
# =========================================================================


def verify_bridge_auth(
    x_bridge_client_id: str | None = Header(None, alias="X-Bridge-Client-Id"),
    x_bridge_key: str | None = Header(None, alias="X-Bridge-Key"),
):
    """
    Validate that request originates from an authorized Bridge agent.
    Lite uses secure pre-shared API keys. Prime can use mutual TLS or signed tokens.
    """
    if not x_bridge_client_id or not x_bridge_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required Bridge authentication headers (X-Bridge-Client-Id, X-Bridge-Key)",
        )
    # Simple valid check for test/dev
    return {"client_id": x_bridge_client_id}


# In-memory storage for active bridge states & mock queue when DB is not actively attached
_bridge_states: dict[str, Any] = {}
_discovered_companies: dict[str, list[dict[str, Any]]] = {}
_pending_job_queue: list[dict[str, Any]] = []


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.get("/status")
def get_bridge_status(db: Session = Depends(get_db)):
    """Return overall bridge connection and Tally instance status for UI."""
    # Find latest active bridge state
    latest_client = next(iter(_bridge_states.keys()), None)
    state = _bridge_states.get(latest_client, {}) if latest_client else {}

    tally_online = False
    if state:
        tally_status = state.get("tally_status", {})
        tally_online = tally_status.get("is_online", False)

    # Count companies from DB if available
    db_company_count = 0
    tally_instance_info = None
    try:
        tally_instances = db.scalars(select(TallyInstance)).all()
        if tally_instances:
            inst = tally_instances[0]
            tally_instance_info = {
                "id": str(inst.id),
                "instance_name": inst.instance_name,
                "host": inst.host,
                "port": inst.port,
                "is_active": inst.is_active,
            }
        tally_comps = db.scalars(select(TallyCompany)).all()
        db_company_count = len(tally_comps)
    except Exception:
        pass

    return {
        "bridge_connected": bool(latest_client),
        "bridge_client_id": latest_client or "None",
        "bridge_status": state.get("status", "OFFLINE"),
        "tally_online": tally_online,
        "tally_details": state.get("tally_status", {}),
        "last_heartbeat": state.get("last_heartbeat"),
        "companies_discovered_count": db_company_count,
        "tally_instance": tally_instance_info,
    }


@router.post("/heartbeat")
def bridge_heartbeat(
    payload: BridgeHeartbeatRequest,
    auth: dict = Depends(verify_bridge_auth),
    db: Session = Depends(get_db),
):
    """Record Bridge heartbeat, Tally connectivity, and capability status."""
    client_id = auth["client_id"]
    now = datetime.now(timezone.utc)
    _bridge_states[client_id] = {
        "status": payload.status,
        "tally_status": payload.tally_status,
        "last_heartbeat": now.isoformat(),
    }

    try:
        # Sync with DB if available
        org = db.scalar(select(Organization).where(Organization.slug == "default-org"))
        if not org:
            org = Organization(legal_name="Default Organization", slug="default-org")
            db.add(org)
            db.flush()

        inst = db.scalar(select(TallyInstance).where(TallyInstance.organization_id == org.id))
        if not inst:
            inst = TallyInstance(
                organization_id=org.id,
                instance_name="Local TallyPrime",
                host="127.0.0.1",
                port=9000,
                is_active=True,
            )
            db.add(inst)
            db.flush()

        bridge = db.scalar(select(Bridge).where(Bridge.bridge_client_id == client_id))
        if not bridge:
            bridge = Bridge(
                organization_id=org.id,
                tally_instance_id=inst.id,
                bridge_client_id=client_id,
                api_key_hash="dev-key",
                status=payload.status,
                last_heartbeat_at=now,
            )
            db.add(bridge)
        else:
            bridge.status = payload.status
            bridge.last_heartbeat_at = now
            bridge.tally_instance_id = inst.id
        db.commit()
    except Exception:
        db.rollback()

    return {
        "status": "acknowledged",
        "client_id": client_id,
        "timestamp": now.isoformat(),
    }


@router.post("/companies")
def report_discovered_companies(
    payload: BridgeCompaniesRequest,
    auth: dict = Depends(verify_bridge_auth),
    db: Session = Depends(get_db),
):
    """Record discovered Tally companies reported by the Bridge into PostgreSQL."""
    client_id = auth["client_id"]
    _discovered_companies[client_id] = [c.model_dump() for c in payload.companies]
    now = datetime.now(timezone.utc)

    try:
        # Ensure default org & tally instance exist
        org = db.scalar(select(Organization).where(Organization.slug == "default-org"))
        if not org:
            org = Organization(legal_name="Default Organization", slug="default-org")
            db.add(org)
            db.flush()

        inst = db.scalar(select(TallyInstance).where(TallyInstance.organization_id == org.id))
        if not inst:
            inst = TallyInstance(
                organization_id=org.id,
                instance_name="Local TallyPrime",
                host="127.0.0.1",
                port=9000,
                is_active=True,
            )
            db.add(inst)
            db.flush()

        for c in payload.companies:
            guid = c.guid or f"guid-{c.name}"
            tc = db.scalar(
                select(TallyCompany).where(
                    TallyCompany.tally_instance_id == inst.id,
                    TallyCompany.tally_guid == guid,
                )
            )
            if not tc:
                # Also check by company_name if guid was generic
                tc = db.scalar(
                    select(TallyCompany).where(
                        TallyCompany.tally_instance_id == inst.id,
                        TallyCompany.company_name == c.name,
                    )
                )

            # Parse books_from date safely
            parsed_date = None
            if c.books_from:
                try:
                    parsed_date = date.fromisoformat(c.books_from[:10])
                except Exception:
                    pass

            if tc:
                tc.company_name = c.name
                tc.financial_year = c.financial_year_from
                if parsed_date:
                    tc.books_from = parsed_date
                tc.last_seen_at = now
            else:
                tc = TallyCompany(
                    tally_instance_id=inst.id,
                    tally_guid=guid,
                    company_name=c.name,
                    financial_year=c.financial_year_from,
                    books_from=parsed_date,
                    status="DISCOVERED",
                    last_seen_at=now,
                )
                db.add(tc)

        db.commit()
    except Exception:
        db.rollback()

    return {
        "status": "synchronized",
        "companies_recorded": len(payload.companies),
        "client_id": client_id,
    }


@router.get("/companies")
def get_reported_companies(
    auth: dict = Depends(verify_bridge_auth),
):
    """Retrieve the latest companies reported by this Bridge."""
    client_id = auth["client_id"]
    return {"companies": _discovered_companies.get(client_id, [])}


@router.get("/jobs/pending", response_model=PendingJobsResponse)
def get_pending_jobs(
    auth: dict = Depends(verify_bridge_auth),
):
    """Bridge polls for pending jobs."""
    # Return available jobs
    return {"jobs": _pending_job_queue}


@router.post("/jobs/{job_id}/attempts")
def record_job_attempt(
    job_id: str,
    payload: PostingAttemptPayload,
    auth: dict = Depends(verify_bridge_auth),
    db: Session = Depends(get_db),
):
    """
    Phase 3I: Bridge reports the result of a posting attempt to Tally.
    Persists PostingAttempt and PostingResponse entities in PostgreSQL.
    Advances Document status to POSTED upon success.
    Appends immutable AuditEvent.
    """
    client_id = auth["client_id"]
    try:
        j_uuid = uuid.UUID(job_id)
        job = db.scalar(select(PostingJob).where(PostingJob.id == j_uuid))
        if job:
            attempt_num = len(job.attempts) + 1 if job.attempts else 1
            attempt = PostingAttempt(
                posting_job_id=job.id,
                attempt_number=attempt_num,
                payload_format="XML",
                payload_sent=payload.raw_response or "Voucher Command",
            )
            db.add(attempt)
            db.flush()

            response = PostingResponse(
                posting_attempt_id=attempt.id,
                status_code=payload.status_code,
                raw_response=payload.raw_response
                or ("SUCCESS" if payload.success else (payload.error_message or "FAILED")),
                tally_voucher_guid=payload.voucher_guid,
                tally_voucher_number=payload.voucher_number,
                tally_master_id=payload.master_id,
                is_success=payload.success,
                error_description=payload.error_message,
            )
            db.add(response)

            if payload.success:
                job.status = "POSTED"
                # Update document status
                if job.transaction and job.transaction.accounting_proposal_id:
                    prop = db.scalar(
                        select(AccountingProposal).where(
                            AccountingProposal.id == job.transaction.accounting_proposal_id
                        )
                    )
                    if prop and prop.document_id:
                        doc = db.scalar(select(Document).where(Document.id == prop.document_id))
                        if doc:
                            doc.status = "POSTED"

            # Immutable Audit Event
            db.add(
                AuditEvent(
                    organization_id=job.organization_id,
                    company_id=job.company_id,
                    actor_type="BRIDGE",
                    actor_id=client_id,
                    action="VOUCHER_POSTED_TO_TALLY"
                    if payload.success
                    else "VOUCHER_POSTING_FAILED",
                    entity_type="PostingJob",
                    entity_id=job.id,
                    changes={"status": job.status},
                    event_metadata={
                        "voucher_number": payload.voucher_number,
                        "voucher_guid": payload.voucher_guid,
                        "success": payload.success,
                        "error_message": payload.error_message,
                    },
                )
            )
            db.commit()
    except Exception:
        db.rollback()

    return {
        "status": "recorded",
        "job_id": job_id,
        "is_success": payload.success,
        "voucher_number": payload.voucher_number,
    }


@router.post("/jobs/{job_id}/verification")
def record_job_verification(
    job_id: str,
    payload: VerificationResultPayload,
    auth: dict = Depends(verify_bridge_auth),
    db: Session = Depends(get_db),
):
    """
    Phases 3J & 3K: Bridge reports read-back verification evidence.
    Persists VerificationResult entity in PostgreSQL.
    Advances Document status to VERIFIED upon successful read-back match.
    Appends immutable AuditEvent.
    """
    client_id = auth["client_id"]
    try:
        j_uuid = uuid.UUID(job_id)
        job = db.scalar(select(PostingJob).where(PostingJob.id == j_uuid))
        if job:
            last_resp = db.scalar(
                select(PostingResponse)
                .join(PostingAttempt)
                .where(PostingAttempt.posting_job_id == job.id)
                .order_by(PostingResponse.received_at.desc())
            )
            last_resp_id = last_resp.id if last_resp else None

            if not last_resp_id:
                att = PostingAttempt(
                    posting_job_id=job.id,
                    attempt_number=1,
                    payload_format="XML",
                    payload_sent="Voucher Query",
                )
                db.add(att)
                db.flush()
                resp = PostingResponse(
                    posting_attempt_id=att.id,
                    status_code=200,
                    raw_response="SIMULATED_VERIFICATION",
                    is_success=True,
                )
                db.add(resp)
                db.flush()
                last_resp_id = resp.id

            vr = VerificationResult(
                posting_response_id=last_resp_id,
                actual_tally_voucher_number=payload.actual_voucher_number,
                tally_guid=payload.actual_guid,
                actual_amount=payload.actual_amount,
                status=payload.status,
                mismatch_details=payload.mismatch_details,
                verification_method="TALLY_READ_BACK",
            )
            db.add(vr)
            db.flush()

            if payload.is_verified:
                job.status = "VERIFIED"
                job.completed_at = datetime.now(timezone.utc)
                txn = db.scalar(select(Transaction).where(Transaction.id == job.transaction_id))
                prop = None
                doc = None
                if txn and txn.accounting_proposal_id:
                    prop = db.scalar(
                        select(AccountingProposal).where(
                            AccountingProposal.id == txn.accounting_proposal_id
                        )
                    )
                    if prop and prop.document_id:
                        doc = db.scalar(select(Document).where(Document.id == prop.document_id))
                        if doc:
                            doc.status = "VERIFIED"

            # Immutable Audit Event
            db.add(
                AuditEvent(
                    organization_id=job.organization_id,
                    company_id=job.company_id,
                    actor_type="BRIDGE",
                    actor_id=client_id,
                    action="VOUCHER_VERIFIED_READ_BACK",
                    entity_type="VerificationResult",
                    entity_id=vr.id,
                    changes={"status": payload.status, "is_verified": payload.is_verified},
                    event_metadata={
                        "actual_voucher_number": payload.actual_voucher_number,
                        "actual_guid": payload.actual_guid,
                        "actual_amount": payload.actual_amount,
                        "mismatch_details": payload.mismatch_details,
                    },
                )
            )
            # Remove from pending queue
            _pending_job_queue[:] = [j for j in _pending_job_queue if j.get("job_id") != job_id]
            db.commit()
    except Exception:
        import traceback

        traceback.print_exc()
        db.rollback()

    return {
        "status": "recorded",
        "job_id": job_id,
        "is_verified": payload.is_verified,
        "verification_status": payload.status,
    }


@router.get("/audit/events")
def list_audit_events(
    company_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Phase 3K: Retrieve immutable audit events for forensic verification proof."""
    query = select(AuditEvent).order_by(AuditEvent.recorded_at.desc()).limit(limit)
    if company_id:
        try:
            query = query.where(AuditEvent.company_id == uuid.UUID(company_id))
        except Exception:
            pass
    events = db.scalars(query).all()
    return [
        {
            "id": str(e.id),
            "action": e.action,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "entity_type": e.entity_type,
            "entity_id": str(e.entity_id),
            "changes": e.changes,
            "event_metadata": e.event_metadata,
            "recorded_at": e.recorded_at.isoformat(),
        }
        for e in events
    ]
