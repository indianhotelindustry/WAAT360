import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.database import SessionLocal, get_db
from src.forensics.knowledge_service import KnowledgeService
from src.main import app
from src.models.entities import Company, Organization
from src.models.knowledge_entities import (
    KnowledgeSource,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def two_companies(db_session: Session):
    org = Organization(
        legal_name="Multi-Tenant Health Check Org", slug=f"mthc-{uuid.uuid4().hex[:6]}"
    )
    db_session.add(org)
    db_session.flush()

    comp_a = Company(
        organization_id=org.id,
        legal_name="Company Alpha Technologies Ltd",
        gstin="27AAACT2727Q1ZW",
    )
    comp_b = Company(
        organization_id=org.id,
        legal_name="Company Beta Logistics Ltd",
        gstin="24AAACB1111Q1ZX",
    )
    db_session.add_all([comp_a, comp_b])
    db_session.commit()
    db_session.refresh(comp_a)
    db_session.refresh(comp_b)
    return comp_a, comp_b


# =========================================================================
# 1. KNOWLEDGE CORE TESTS: PROVENANCE, VERSIONING, DATES
# =========================================================================


def test_knowledge_core_provenance_and_versioning(client: TestClient, db_session: Session):
    KnowledgeService.seed_initial_knowledge(db_session)

    # 1. Verify sources have authoritative provenance
    sources = db_session.query(KnowledgeSource).all()
    assert len(sources) >= 4
    source_codes = [s.source_code for s in sources]
    assert "SRC-CBIC-GST-01" in source_codes
    assert "SRC-CBDT-TDS-01" in source_codes
    assert "SRC-ICAI-AS-01" in source_codes
    assert "SRC-TALLY-DOC-01" in source_codes

    cbic = db_session.query(KnowledgeSource).filter_by(source_code="SRC-CBIC-GST-01").first()
    assert cbic.source_type == "OFFICIAL_AUTHORITATIVE"
    assert cbic.is_verified is True
    assert "CBIC" in cbic.authority_name

    # 2. Query Knowledge Items via API
    res = client.get("/api/v1/health-check/knowledge")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 5

    # Check GST rule KN-GST-001 has date and source
    gst_rule = next(i for i in items if i["knowledge_code"] == "KN-GST-001")
    assert gst_rule["domain"] == "GST_TAX"
    assert gst_rule["effective_from"] == "2017-07-01"
    assert gst_rule["rule_version"] == 1
    assert gst_rule["status"] == "ACTIVE"
    assert gst_rule["source"]["source_code"] == "SRC-CBIC-GST-01"

    # 3. Test temporal date validity
    active_items = KnowledgeService.get_knowledge_items(db_session, effective_on=date(2026, 9, 23))
    assert len(active_items) >= 5

    pre_gst_items = KnowledgeService.get_knowledge_items(db_session, effective_on=date(2010, 1, 1))
    pre_gst_codes = [i.knowledge_code for i in pre_gst_items]
    assert "KN-ACC-001" in pre_gst_codes
    assert "KN-GST-001" not in pre_gst_codes  # Not effective before July 2017!


# =========================================================================
# 2. MULTI-TENANT ISOLATION TESTS
# =========================================================================


def test_decision_memory_multi_tenant_isolation(
    client: TestClient, db_session: Session, two_companies
):
    comp_a, comp_b = two_companies

    # Record decision memory for Company A
    KnowledgeService.record_decision_memory(
        db=db_session,
        company_id=comp_a.id,
        finding_code="FIND-LED-001",
        rule_code="FOR-LED-001",
        entity_type="LEDGER",
        entity_name="ABC Traders",
        current_state={"parent_group": "Indirect Expenses"},
        recommended_state={"parent_group": "Sundry Creditors"},
        decision_reason="Authorized accounting policy override for Company Alpha",
        actor_id="controller@alpha.com",
    )

    # 1. Company A MUST find the decision memory
    dec_a = KnowledgeService.find_active_decision_memory(
        db=db_session,
        company_id=comp_a.id,
        rule_code="FOR-LED-001",
        entity_name="ABC Traders",
    )
    assert dec_a is not None
    assert dec_a.company_id == comp_a.id

    # 2. Company B MUST NOT find Company A's decision memory (Strict Multi-Tenant Boundary)
    dec_b = KnowledgeService.find_active_decision_memory(
        db=db_session,
        company_id=comp_b.id,
        rule_code="FOR-LED-001",
        entity_name="ABC Traders",
    )
    assert dec_b is None


# =========================================================================
# 3. ACCOUNTING HEALTH CHECK FORENSIC SCAN & EVIDENCE TESTS
# =========================================================================


def test_accounting_health_check_scan_and_findings(
    client: TestClient, db_session: Session, two_companies
):
    comp_a, _ = two_companies

    # Run scan
    res = client.post(f"/api/v1/health-check/scans/run?company_id={comp_a.id}")
    assert res.status_code == 200
    scan = res.json()

    assert scan["scan_status"] == "COMPLETED"
    assert scan["ledgers_reviewed"] >= 15
    assert scan["findings_count"] >= 3
    assert scan["overall_health"] in ["REVIEW_RECOMMENDED", "CRITICAL_FINDINGS"]

    findings = scan["findings"]
    rule_codes = [f["rule_code"] for f in findings]

    # Verify Rule 1: Trade vendor misclassified under Indirect Expenses
    assert "FOR-LED-001" in rule_codes
    led_finding = next(f for f in findings if f["rule_code"] == "FOR-LED-001")
    assert led_finding["entity_name"] == "ABC Traders"
    assert led_finding["severity"] == "REVIEW_RECOMMENDED"
    assert "Indirect Expenses" in led_finding["fact_observed"]
    assert led_finding["knowledge_code"] == "KN-ACC-001"
    assert led_finding["decision_status"] == "PENDING_REVIEW"

    # Verify Rule 2: Duplicate master cluster
    assert "FOR-DUP-001" in rule_codes
    dup_finding = next(f for f in findings if f["rule_code"] == "FOR-DUP-001")
    assert "Freight" in dup_finding["entity_name"]

    # Verify Rule 3: GST review
    assert "FOR-GST-001" in rule_codes
    gst_finding = next(f for f in findings if f["rule_code"] == "FOR-GST-001")
    assert gst_finding["severity"] == "CRITICAL"


# =========================================================================
# 4. DECISION MEMORY: TRANSPARENT KNOWN EXCEPTION (NOT BLIND SUPPRESSION)
# =========================================================================


def test_decision_memory_preserves_forensic_transparency(
    client: TestClient, db_session: Session, two_companies
):
    comp_a, _ = two_companies

    # 1. Run initial scan
    scan1_res = client.post(f"/api/v1/health-check/scans/run?company_id={comp_a.id}")
    scan1 = scan1_res.json()
    finding = next(f for f in scan1["findings"] if f["rule_code"] == "FOR-LED-001")
    finding_id = finding["id"]

    # 2. Record human decision: "Intentional and approved"
    dec_res = client.post(
        f"/api/v1/health-check/findings/{finding_id}/record-decision",
        json={
            "decision_reason": "Controller approved as unique subsidiary ledger arrangement",
            "actor_id": "auditor@waast360.local",
            "actor_role": "CONTROLLER",
        },
    )
    assert dec_res.status_code == 200
    dec_data = dec_res.json()
    assert dec_data["decision_status"] == "KNOWN_EXCEPTION"
    assert dec_data["known_exception_id"] is not None

    # 3. Re-run scan: Rule is NOT deleted; finding reappears with KNOWN_EXCEPTION status!
    scan2_res = client.post(f"/api/v1/health-check/scans/run?company_id={comp_a.id}")
    scan2 = scan2_res.json()
    assert scan2["known_exceptions_count"] >= 1

    finding_rerun = next(f for f in scan2["findings"] if f["rule_code"] == "FOR-LED-001")
    assert finding_rerun["decision_status"] == "KNOWN_EXCEPTION"
    assert finding_rerun["known_exception_id"] is not None


# =========================================================================
# 5. CORRECTION CENTER: PROPOSAL, APPROVAL & BEFORE/AFTER VERIFICATION
# =========================================================================


def test_correction_center_lifecycle_and_stale_protection(
    client: TestClient, db_session: Session, two_companies
):
    comp_a, _ = two_companies

    # 1. Run scan to get finding
    scan_res = client.post(f"/api/v1/health-check/scans/run?company_id={comp_a.id}")
    findings = scan_res.json()["findings"]
    finding = next(f for f in findings if f["rule_code"] == "FOR-LED-001")
    finding_id = finding["id"]

    # 2. Propose Correction
    prop_res = client.post(
        f"/api/v1/health-check/findings/{finding_id}/propose-correction",
        json={"new_parent_group": "Sundry Creditors"},
    )
    assert prop_res.status_code == 200
    prop = prop_res.json()
    prop_id = prop["id"]
    assert prop["status"] == "APPROVAL_REQUIRED"
    assert prop["before_state"]["parent_group"] == "Indirect Expenses"
    assert prop["proposed_state"]["parent_group"] == "Sundry Creditors"

    # 3. Unapproved execution MUST be rejected (Amendment 4)
    exec_unapproved = client.post(f"/api/v1/health-check/corrections/{prop_id}/execute")
    assert exec_unapproved.status_code == 400
    assert "EXECUTION_ELIGIBLE" in exec_unapproved.json()["detail"]

    # 4. Authoritative Approval
    appr_res = client.post(
        f"/api/v1/health-check/corrections/{prop_id}/approve",
        json={"comments": "Reclassification audited and approved", "approver_role": "CONTROLLER"},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "EXECUTION_ELIGIBLE"

    # 5. Execute via Bridge and verify before/after read-back
    exec_res = client.post(f"/api/v1/health-check/corrections/{prop_id}/execute")
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["status"] == "VERIFIED"
    assert exec_data["before_group"] == "Indirect Expenses"
    assert exec_data["after_group"] == "Sundry Creditors"
    assert exec_data["read_back_evidence"]["verified"] is True
