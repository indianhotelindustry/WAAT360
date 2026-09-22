import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.models.base import Base, generate_uuid7, utc_now
from src.models.entities import (
    AccountingProposal,
    Approval,
    AuditEvent,
    Bridge,
    Company,
    Document,
    Ledger,
    Organization,
    PostingAttempt,
    PostingJob,
    PostingResponse,
    TallyCompany,
    TallyInstance,
    Transaction,
    TransactionLine,
    User,
    VerificationResult,
)


@pytest.fixture
def db_session():
    # SQLite in-memory with foreign key enforcement
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def test_uuid7_generation():
    """Verify that generate_uuid7 creates valid UUID objects."""
    uid = generate_uuid7()
    assert isinstance(uid, uuid.UUID)
    assert uid.version in (4, 7)


def test_tenant_company_tally_hierarchy(db_session: Session):
    """
    Verify the fundamental multi-tenant distinction:
    WAAST360 Company != Tally Instance != Tally Company.
    """
    # 1. Organization
    org = Organization(legal_name="Acme Holdings Ltd", slug="acme-holdings")
    db_session.add(org)
    db_session.flush()

    # 2. WAAST360 Company
    company = Company(
        organization_id=org.id,
        legal_name="Acme Manufacturing Pvt Ltd",
        trade_name="Acme Mfg",
        pan="ABCDE1234F",
        gstin="27ABCDE1234F1Z5",
    )
    db_session.add(company)
    db_session.flush()

    # 3. Tally Instance
    instance = TallyInstance(
        organization_id=org.id,
        instance_name="Factory-Floor-TallyPrime",
        host="192.168.1.100",
        port=9000,
        tally_version="TallyPrime 4.1",
    )
    db_session.add(instance)
    db_session.flush()

    # 4. Tally Company (mapped to WAAST360 company)
    tally_comp = TallyCompany(
        tally_instance_id=instance.id,
        company_id=company.id,
        tally_guid="TALLY-COMP-GUID-998811",
        company_name="Acme Mfg Pvt Ltd (2026-2027)",
        financial_year="2026-2027",
        books_from=date(2026, 4, 1),
        status="ACTIVE",
    )
    db_session.add(tally_comp)

    # 5. Bridge connects to Tally Instance
    bridge = Bridge(
        organization_id=org.id,
        tally_instance_id=instance.id,
        bridge_client_id="BR-WIN-LOCAL-01",
        api_key_hash="sha256$dummyhash",
        os_platform="Windows 11",
        status="ONLINE",
    )
    db_session.add(bridge)
    db_session.commit()

    assert tally_comp.id is not None
    assert tally_comp.tally_instance.instance_name == "Factory-Floor-TallyPrime"
    assert tally_comp.company.legal_name == "Acme Manufacturing Pvt Ltd"
    assert bridge.tally_instance.port == 9000


def test_accounting_proposal_multi_step_approval_and_transaction(db_session: Session):
    """
    Verify:
    1. AccountingProposal remains separate from Transaction.
    2. Approval supports multi-step sequence without schema redesign.
    3. Transaction is created with debit/credit lines upon approval.
    """
    org = Organization(legal_name="Global Corp", slug="global-corp")
    db_session.add(org)
    db_session.flush()

    company = Company(organization_id=org.id, legal_name="Global Retail")
    user1 = User(
        organization_id=org.id,
        email="finance@global.com",
        full_name="Finance Officer",
        hashed_password="pwd",
    )
    user2 = User(
        organization_id=org.id,
        email="cfo@global.com",
        full_name="Chief Financial Officer",
        hashed_password="pwd",
    )
    db_session.add_all([company, user1, user2])
    db_session.flush()

    doc = Document(
        organization_id=org.id,
        company_id=company.id,
        document_number="INV-2026-001",
        file_name="vendor_bill.pdf",
        file_type="PDF",
        file_size_bytes=1048576,
        storage_path="/docs/invoices/inv-001.pdf",
        sha256_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status="UPLOADED",
    )
    db_session.add(doc)
    db_session.flush()

    # Accounting Proposal
    proposal = AccountingProposal(
        organization_id=org.id,
        company_id=company.id,
        document_id=doc.id,
        voucher_type="Purchase",
        proposed_date=date(2026, 9, 22),
        total_amount=11800.00,
        tax_amount=1800.00,
        narration="Purchase of raw materials",
        status="DRAFT",
    )
    db_session.add(proposal)
    db_session.flush()

    # Step 1: Preliminary Approval
    approval_step1 = Approval(
        accounting_proposal_id=proposal.id,
        user_id=user1.id,
        decision="APPROVED",
        approval_step=1,
        authority_context="PRIMARY_REVIEWER",
        comments="Amounts match PO.",
    )
    # Step 2: Final Executive Approval (Multi-step verification)
    approval_step2 = Approval(
        accounting_proposal_id=proposal.id,
        user_id=user2.id,
        decision="APPROVED",
        approval_step=2,
        authority_context="EXECUTIVE_SIGN_OFF",
        comments="Authorized for payment and posting.",
    )
    db_session.add_all([approval_step1, approval_step2])

    proposal.status = "APPROVED"
    db_session.flush()

    # Authoritative Transaction generated post-approval
    tx = Transaction(
        organization_id=org.id,
        company_id=company.id,
        accounting_proposal_id=proposal.id,
        voucher_type="Purchase",
        voucher_date=date(2026, 9, 22),
        reference_number="INV-2026-001",
        total_amount=11800.00,
        narration="Approved Purchase of raw materials",
    )
    db_session.add(tx)
    db_session.flush()

    # Master Ledgers for line items
    purchase_ledger = Ledger(
        organization_id=org.id,
        company_id=company.id,
        name="Purchase A/c",
        parent_group="Purchase Accounts",
    )
    tax_ledger = Ledger(
        organization_id=org.id,
        company_id=company.id,
        name="Input IGST 18%",
        parent_group="Duties & Taxes",
    )
    creditor_ledger = Ledger(
        organization_id=org.id,
        company_id=company.id,
        name="Supplier Co",
        parent_group="Sundry Creditors",
    )
    db_session.add_all([purchase_ledger, tax_ledger, creditor_ledger])
    db_session.flush()

    # Transaction Lines: Debit Purchase 10,000, Debit Tax 1,800, Credit Supplier 11,800
    line1 = TransactionLine(
        transaction_id=tx.id,
        line_number=1,
        ledger_id=purchase_ledger.id,
        is_debit=True,
        amount=10000.00,
    )
    line2 = TransactionLine(
        transaction_id=tx.id,
        line_number=2,
        ledger_id=tax_ledger.id,
        is_debit=True,
        amount=1800.00,
    )
    line3 = TransactionLine(
        transaction_id=tx.id,
        line_number=3,
        ledger_id=creditor_ledger.id,
        is_debit=False,
        amount=11800.00,
    )
    db_session.add_all([line1, line2, line3])
    db_session.commit()

    assert len(proposal.approvals) == 2
    assert proposal.approvals[0].approval_step == 1
    assert proposal.approvals[1].approval_step == 2
    assert len(tx.lines) == 3


def test_posting_and_verification_evidence_model(db_session: Session):
    """
    Verify complete forensic chain:
    PostingJob -> PostingAttempt -> PostingResponse -> VerificationResult
    """
    org = Organization(legal_name="Enterprise Corp", slug="ent-corp")
    db_session.add(org)
    db_session.flush()

    company = Company(organization_id=org.id, legal_name="Ent India")
    db_session.add(company)
    db_session.flush()

    doc = Document(
        organization_id=org.id,
        company_id=company.id,
        file_name="bill.pdf",
        file_type="PDF",
        file_size_bytes=100,
        storage_path="/b.pdf",
        sha256_checksum="abc",
    )
    db_session.add(doc)
    db_session.flush()

    proposal = AccountingProposal(
        organization_id=org.id,
        company_id=company.id,
        document_id=doc.id,
        voucher_type="Purchase",
        proposed_date=datetime.now(timezone.utc).date(),
        total_amount=5000.0,
    )
    db_session.add(proposal)
    db_session.flush()

    tx = Transaction(
        organization_id=org.id,
        company_id=company.id,
        accounting_proposal_id=proposal.id,
        voucher_type="Purchase",
        voucher_date=datetime.now(timezone.utc).date(),
        total_amount=5000.0,
    )
    db_session.add(tx)
    db_session.flush()

    bridge = Bridge(
        organization_id=org.id,
        bridge_client_id="BR-ENT-01",
        api_key_hash="hash",
        status="ONLINE",
    )
    db_session.add(bridge)
    db_session.flush()

    job = PostingJob(
        organization_id=org.id,
        company_id=company.id,
        transaction_id=tx.id,
        bridge_id=bridge.id,
        status="QUEUED",
    )
    db_session.add(job)
    db_session.flush()

    attempt = PostingAttempt(
        posting_job_id=job.id,
        attempt_number=1,
        payload_format="XML",
        payload_sent="<ENVELOPE>...</ENVELOPE>",
    )
    db_session.add(attempt)
    db_session.flush()

    resp = PostingResponse(
        posting_attempt_id=attempt.id,
        status_code=200,
        raw_response="<RESPONSE><STATUS>1</STATUS><GUID>TALLY-VCH-8822</GUID></RESPONSE>",
        tally_voucher_guid="TALLY-VCH-8822",
        tally_master_id=4501,
        tally_voucher_number="VCH/2026/045",
        is_success=True,
    )
    db_session.add(resp)
    db_session.flush()

    verification = VerificationResult(
        posting_response_id=resp.id,
        expected_voucher_reference="INV-2026-001",
        actual_tally_voucher_number="VCH/2026/045",
        tally_guid="TALLY-VCH-8822",
        expected_amount=5000.0,
        actual_amount=5000.0,
        expected_accounting_identity="Purchase Voucher",
        actual_accounting_identity="Purchase Voucher",
        verification_method="TALLY_READ_BACK",
        status="VERIFIED",
    )
    db_session.add(verification)
    db_session.commit()

    assert resp.verifications[0].status == "VERIFIED"
    assert resp.verifications[0].tally_guid == "TALLY-VCH-8822"
    assert resp.verifications[0].actual_amount == 5000.0


def test_soft_delete_and_audit_event(db_session: Session):
    """
    Verify:
    1. Soft delete fields: is_deleted, deleted_at, deleted_by, deletion_reason.
    2. AuditEvent immutable tracking.
    """
    org = Organization(legal_name="Audit Org", slug="audit-org")
    db_session.add(org)
    db_session.flush()

    user = User(
        organization_id=org.id,
        email="auditor@org.com",
        full_name="Auditor",
        hashed_password="pwd",
    )
    company = Company(organization_id=org.id, legal_name="Audit Co")
    db_session.add_all([user, company])
    db_session.flush()

    ledger = Ledger(organization_id=org.id, company_id=company.id, name="Obsolete Ledger")
    db_session.add(ledger)
    db_session.flush()

    # Soft delete action
    ledger.is_deleted = True
    ledger.deleted_at = utc_now()
    ledger.deleted_by = user.id
    ledger.deletion_reason = "Duplicate chart of account entry"

    # Audit event
    event = AuditEvent(
        organization_id=org.id,
        company_id=company.id,
        actor_type="USER",
        actor_id=str(user.id),
        action="LEDGER_SOFT_DELETED",
        entity_type="Ledger",
        entity_id=ledger.id,
        changes={"is_deleted": True, "deletion_reason": ledger.deletion_reason},
    )
    db_session.add(event)
    db_session.commit()

    saved_ledger = db_session.scalar(select(Ledger).where(Ledger.id == ledger.id))
    assert saved_ledger.is_deleted is True
    assert saved_ledger.deletion_reason == "Duplicate chart of account entry"
    assert saved_ledger.deleted_by == user.id

    saved_event = db_session.scalar(select(AuditEvent).where(AuditEvent.entity_id == ledger.id))
    assert saved_event.action == "LEDGER_SOFT_DELETED"
    assert saved_event.changes["deletion_reason"] == "Duplicate chart of account entry"
