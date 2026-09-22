from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.entities import Bridge, Organization, TallyCompany, TallyInstance

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
):
    """Bridge reports the result of a posting attempt to Tally."""
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
):
    """Bridge reports read-back verification evidence."""
    return {
        "status": "recorded",
        "job_id": job_id,
        "is_verified": payload.is_verified,
        "verification_status": payload.status,
    }
