import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.core.bridge_loader import get_simulated_adapter_class
from src.core.database import get_db
from src.forensics.health_checker import AccountingHealthChecker
from src.forensics.knowledge_service import KnowledgeService
from src.models.entities import AuditEvent, Company, TallyCompany
from src.models.knowledge_entities import (
    CorrectionJob,
    CorrectionProposal,
    DecisionMemory,
    ForensicFinding,
    ForensicScan,
)

router = APIRouter(prefix="/api/v1/health-check", tags=["Accounting Health Check"])


# =========================================================================
# SCHEMAS
# =========================================================================


class KnowledgeSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_code: str
    authority_name: str
    source_type: str
    reference_url: Optional[str]
    citation: Optional[str]
    jurisdiction: str
    is_verified: bool
    reviewed_by: Optional[str]


class KnowledgeItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    knowledge_code: str
    domain: str
    title: str
    content: str
    jurisdiction: str
    effective_from: str
    effective_until: Optional[str]
    rule_version: int
    tally_version_pattern: Optional[str]
    status: str
    confidence: float
    source: Optional[KnowledgeSourceResponse] = None


class DecisionMemoryRequest(BaseModel):
    decision_reason: str
    actor_id: str = "controller@waast360.local"
    actor_role: str = "CONTROLLER"


class ProposeCorrectionRequest(BaseModel):
    new_parent_group: str = "Sundry Creditors"


class ApproveCorrectionRequest(BaseModel):
    approver_role: str = "CONTROLLER"
    comments: str = "Reviewed and approved master reclassification"
    approval_signature: Optional[str] = None


class ForensicFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    scan_id: uuid.UUID
    company_id: uuid.UUID
    finding_code: str
    rule_code: str
    entity_type: str
    entity_name: str
    severity: str
    fact_observed: str
    fact_details: Dict[str, Any]
    rule_triggered: str
    knowledge_code: Optional[str]
    recommendation: str
    decision_status: str
    known_exception_id: Optional[uuid.UUID]
    created_at: datetime


class ForensicScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    scan_code: str
    scan_status: str
    ledgers_reviewed: int
    findings_count: int
    critical_count: int
    review_recommended_count: int
    healthy_count: int
    gst_findings_count: int
    duplicate_clusters_count: int
    known_exceptions_count: int
    overall_health: str
    scanned_at: datetime
    findings: List[ForensicFindingResponse] = []


class CorrectionProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    finding_id: uuid.UUID
    company_id: uuid.UUID
    target_entity_type: str
    target_entity_name: str
    before_state: Dict[str, Any]
    proposed_state: Dict[str, Any]
    status: str
    approval_id: Optional[uuid.UUID]
    created_at: datetime


class DecisionMemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    finding_code: str
    rule_code: str
    entity_type: str
    entity_name: str
    decision_reason: str
    human_decision: str
    actor_id: str
    actor_role: str
    decided_at: datetime


# =========================================================================
# ENDPOINTS
# =========================================================================


@router.get("/knowledge", response_model=List[KnowledgeItemResponse])
def list_knowledge_items(
    domain: Optional[str] = Query(None),
    status_filter: str = Query("ACTIVE", alias="status"),
    db: Session = Depends(get_db),
):
    """
    Query the versioned WAAST360 Knowledge Core library with provenance attribution.
    """
    KnowledgeService.seed_initial_knowledge(db)
    items = KnowledgeService.get_knowledge_items(db, domain=domain, status=status_filter)
    result = []
    for item in items:
        resp = KnowledgeItemResponse(
            id=item.id,
            knowledge_code=item.knowledge_code,
            domain=item.domain,
            title=item.title,
            content=item.content,
            jurisdiction=item.jurisdiction,
            effective_from=str(item.effective_from),
            effective_until=str(item.effective_until) if item.effective_until else None,
            rule_version=item.rule_version,
            tally_version_pattern=item.tally_version_pattern,
            status=item.status,
            confidence=float(item.confidence),
            source=KnowledgeSourceResponse.model_validate(item.source) if item.source else None,
        )
        result.append(resp)
    return result


@router.post("/scans/run", response_model=ForensicScanResponse)
def run_accounting_health_check(
    company_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    """
    Run an on-demand Accounting Health Check forensic review for the specified company.
    Queries active Tally snapshot or synthetic demonstration store.
    """
    KnowledgeService.seed_initial_knowledge(db)

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Determine Tally company binding
    tally_company = db.scalars(
        select(TallyCompany).where(TallyCompany.company_id == company.id)
    ).first()

    # Fetch ledgers and parties via TallySimulatedAdapter
    simulated_cls = get_simulated_adapter_class()
    adapter = simulated_cls()

    # Dynamic company ref
    from src.models.domain import TallyCompanyRef

    comp_ref = TallyCompanyRef(
        company_name=tally_company.company_name
        if tally_company
        else "Synthetic Demonstration Company"
    )

    tally_ledgers = adapter.get_ledgers(comp_ref)
    tally_parties = adapter.get_parties(comp_ref)

    ledgers_payload = [
        {"name": ldg.name, "parent_group": ldg.parent_group, "opening_balance": ldg.opening_balance}
        for ldg in tally_ledgers
    ]
    parties_payload = [
        {"name": p.name, "party_type": p.party_type, "parent_group": p.parent_group}
        for p in tally_parties
    ]

    scan = AccountingHealthChecker.run_health_check(
        db=db,
        company_id=company.id,
        company_name=company.legal_name,
        tally_company_id=tally_company.id if tally_company else None,
        ledgers=ledgers_payload,
        parties=parties_payload,
    )

    # Append AuditEvent
    audit = AuditEvent(
        organization_id=company.organization_id,
        company_id=company.id,
        actor_type="SYSTEM_RULE",
        actor_id="FORENSIC_ENGINE",
        action="HEALTH_CHECK_SCAN_EXECUTED",
        entity_type="ForensicScan",
        entity_id=scan.id,
        changes={
            "overall_health": scan.overall_health,
            "ledgers_reviewed": scan.ledgers_reviewed,
            "findings_count": scan.findings_count,
            "critical_count": scan.critical_count,
        },
    )
    db.add(audit)
    db.commit()

    return scan


@router.get("/scans/{company_id}/latest", response_model=ForensicScanResponse)
def get_latest_health_check_scan(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieve the most recent ForensicScan and findings for a company.
    """
    stmt = (
        select(ForensicScan)
        .where(ForensicScan.company_id == company_id)
        .order_by(desc(ForensicScan.scanned_at))
    )
    scan = db.scalars(stmt).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No health check scan found. Run /health-check/scans/run first.",
        )
    return scan


@router.post("/findings/{finding_id}/record-decision", response_model=ForensicFindingResponse)
def record_finding_decision(
    finding_id: uuid.UUID,
    req: DecisionMemoryRequest,
    db: Session = Depends(get_db),
):
    """
    Records an authorized accountant decision confirming that an observed configuration
    is intentional. Does NOT silently delete the finding; marks it as a KNOWN EXCEPTION.
    """
    finding = db.get(ForensicFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    decision = KnowledgeService.record_decision_memory(
        db=db,
        company_id=finding.company_id,
        finding_code=finding.finding_code,
        rule_code=finding.rule_code,
        entity_type=finding.entity_type,
        entity_name=finding.entity_name,
        current_state=finding.fact_details,
        recommended_state={"action": finding.recommendation},
        decision_reason=req.decision_reason,
        actor_id=req.actor_id,
        actor_role=req.actor_role,
        human_decision="KNOWN_EXCEPTION",
    )

    finding.decision_status = "KNOWN_EXCEPTION"
    finding.known_exception_id = decision.id
    db.commit()
    db.refresh(finding)
    return finding


@router.post("/findings/{finding_id}/propose-correction", response_model=CorrectionProposalResponse)
def propose_finding_correction(
    finding_id: uuid.UUID,
    req: ProposeCorrectionRequest,
    db: Session = Depends(get_db),
):
    """
    Formulates a controlled CorrectionProposal to remediate a forensic finding.
    Enforces status: APPROVAL_REQUIRED.
    """
    finding = db.get(ForensicFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    # Check for existing open proposal
    stmt = select(CorrectionProposal).where(
        (CorrectionProposal.finding_id == finding.id)
        & (
            CorrectionProposal.status.in_(
                ["PROPOSED", "APPROVAL_REQUIRED", "APPROVED", "EXECUTION_ELIGIBLE"]
            )
        )
    )
    existing = db.scalars(stmt).first()
    if existing:
        return existing

    proposal = CorrectionProposal(
        finding_id=finding.id,
        company_id=finding.company_id,
        target_entity_type=finding.entity_type,
        target_entity_name=finding.entity_name,
        before_state={
            "parent_group": finding.fact_details.get("current_parent_group", "Indirect Expenses")
        },
        proposed_state={"parent_group": req.new_parent_group},
        status="APPROVAL_REQUIRED",
    )
    db.add(proposal)
    finding.decision_status = "PROPOSED_CORRECTION"
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post("/corrections/{proposal_id}/approve", response_model=CorrectionProposalResponse)
def approve_correction_proposal(
    proposal_id: uuid.UUID,
    req: ApproveCorrectionRequest,
    db: Session = Depends(get_db),
):
    """
    Authorizes a CorrectionProposal with an immutable Approval record.
    Transitions status to EXECUTION_ELIGIBLE.
    """
    proposal = db.get(CorrectionProposal, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Correction proposal not found"
        )

    if proposal.status not in ["PROPOSED", "APPROVAL_REQUIRED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve proposal in status '{proposal.status}'",
        )

    proposal.status = "EXECUTION_ELIGIBLE"
    proposal.stale_reason = f"Approved by {req.approver_role}: {req.comments}"

    comp = db.get(Company, proposal.company_id)
    org_id = comp.organization_id if comp else uuid.uuid4()

    # Append immutable AuditEvent
    audit = AuditEvent(
        organization_id=org_id,
        company_id=proposal.company_id,
        actor_type="USER",
        actor_id="user-controller-01",
        action="CORRECTION_PROPOSAL_APPROVED",
        entity_type="CorrectionProposal",
        entity_id=proposal.id,
        changes={
            "status": "EXECUTION_ELIGIBLE",
            "approver_role": req.approver_role,
            "comments": req.comments,
            "signature": req.approval_signature or f"SIG-CORR-{uuid.uuid4().hex[:8].upper()}",
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(proposal)
    return proposal


@router.post("/corrections/{proposal_id}/execute")
def execute_correction_and_verify(
    proposal_id: uuid.UUID,
    actor_id: str = Query("controller@waast360.local"),
    db: Session = Depends(get_db),
):
    """
    Executes an approved master correction via Bridge / TallySimulatedAdapter,
    performs mandatory read-back verification against the Tally store,
    and guards against stale target-state mismatch.
    """
    proposal = db.get(CorrectionProposal, proposal_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Correction proposal not found"
        )

    if proposal.status not in ["EXECUTION_ELIGIBLE", "APPROVED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute proposal in status '{proposal.status}'. Must be EXECUTION_ELIGIBLE.",
        )

    # 1. Stale Correction Protection (Amendment 4): Check current Tally state before dispatching
    simulated_cls = get_simulated_adapter_class()
    adapter = simulated_cls()

    from src.models.domain import TallyCompanyRef

    comp_ref = TallyCompanyRef(company_name="Synthetic Demonstration Company")
    current_ledger = adapter.get_ledger(comp_ref, proposal.target_entity_name)

    if not current_ledger:
        proposal.status = "STALE_REJECTED"
        proposal.stale_reason = (
            f"Target ledger '{proposal.target_entity_name}' no longer found in Tally."
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"STOP — stale correction proposal. {proposal.stale_reason} Re-scan required.",
        )

    expected_before = proposal.before_state.get("parent_group", "")
    if current_ledger.parent_group.lower() != expected_before.lower():
        proposal.status = "STALE_REJECTED"
        proposal.stale_reason = (
            f"Tally master changed since proposal was generated! "
            f"Expected before group: '{expected_before}', found: '{current_ledger.parent_group}'."
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"STOP — stale correction proposal. {proposal.stale_reason} Re-scan required.",
        )

    # 2. Bridge Execution: Alter master in Tally
    target_group = proposal.proposed_state.get("parent_group", "Sundry Creditors")
    exec_res = adapter.update_ledger_master(comp_ref, proposal.target_entity_name, target_group)

    if not exec_res.get("updated"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bridge reported failure updating master in Tally.",
        )

    # 3. Read-Back Verification (Amendment 4 & Directive 12: Before vs After evidence)
    evidence = adapter.verify_ledger_master(comp_ref, proposal.target_entity_name, target_group)

    if not evidence.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Read-back verification failed: {evidence.get('reason')}",
        )

    # 4. Record CorrectionJob
    job = CorrectionJob(
        proposal_id=proposal.id,
        company_id=proposal.company_id,
        job_status="SUCCESS",
        execution_actor_id=actor_id,
        target_state_verified=True,
        before_state_captured=proposal.before_state,
        after_state_captured={"parent_group": evidence.get("actual_parent_group")},
        read_back_evidence=evidence,
        verified_at=datetime.now(timezone.utc),
    )
    db.add(job)

    proposal.status = "VERIFIED"

    # Update associated finding
    finding = db.get(ForensicFinding, proposal.finding_id)
    if finding:
        finding.decision_status = "CORRECTED"

    # Append AuditEvent
    comp = db.get(Company, proposal.company_id)
    org_id = comp.organization_id if comp else uuid.uuid4()
    audit = AuditEvent(
        organization_id=org_id,
        company_id=proposal.company_id,
        actor_type="USER",
        actor_id=actor_id,
        action="MASTER_CORRECTION_VERIFIED",
        entity_type="CorrectionProposal",
        entity_id=proposal.id,
        changes={
            "ledger_name": proposal.target_entity_name,
            "before_group": expected_before,
            "after_group": evidence.get("actual_parent_group"),
            "verified": True,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "status": "VERIFIED",
        "proposal_id": str(proposal.id),
        "target_entity_name": proposal.target_entity_name,
        "before_group": expected_before,
        "after_group": evidence.get("actual_parent_group"),
        "verified_at": job.verified_at.isoformat(),
        "read_back_evidence": evidence,
    }


@router.get("/corrections", response_model=List[CorrectionProposalResponse])
def list_correction_proposals(
    company_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
):
    """
    List all correction proposals, optionally filtered by company_id.
    """
    stmt = select(CorrectionProposal).order_by(desc(CorrectionProposal.created_at))
    if company_id:
        stmt = stmt.where(CorrectionProposal.company_id == company_id)
    return list(db.scalars(stmt).all())


@router.get("/decisions", response_model=List[DecisionMemoryResponse])
def list_decision_memories(
    company_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
):
    """
    List all audited human decisions & known exceptions, optionally filtered by company_id.
    """
    stmt = select(DecisionMemory).order_by(desc(DecisionMemory.decided_at))
    if company_id:
        stmt = stmt.where(DecisionMemory.company_id == company_id)
    return list(db.scalars(stmt).all())

