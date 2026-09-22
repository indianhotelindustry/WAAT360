import io
import uuid

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

AUTH_HEADERS = {
    "X-Bridge-Client-Id": "BR-TEST-E2E",
    "X-Bridge-Key": "test-key-e2e",
}


def test_full_golden_path_lifecycle():
    """
    PHASE 3L: End-to-End Golden Path Certification Test.
    Covers the full automated lifecycle:
      1. Company Creation & Discovery
      2. Document Ingestion (Phase 3B) -> SHA256 & Duplicate Flagging
      3. AI Extraction (Phase 3C) -> ExtractedInvoiceData & Granular Fields
      4. Accounting Proposal (Phase 3D) -> Balanced Double-Entry Lines
      5. Deterministic Validation (Phase 3E, 3F) -> GST Math, Balance, Duplicates
      6. Human Approval (Phase 3G, 3H) -> Transaction & PostingJob Materialization
      7. Bridge Execution (Phase 3I) -> Posting Attempt Recorded
      8. Read-Back Verification (Phase 3J) -> Forensic Evidence Stored
      9. Audit Trail Verification (Phase 3K) -> Immutable Event Proof
    """
    unique_id = uuid.uuid4().hex[:6]
    company_name = f"Golden Path Org {unique_id} Ltd"

    # =========================================================================
    # Step 1: Create Company
    # =========================================================================
    comp_resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": company_name,
            "trade_name": "Tata Motors Dealership",
            "pan": "AAACT2727Q",
            "gstin": "27AAACT2727Q1ZW",
            "currency": "INR",
        },
    )
    assert comp_resp.status_code == 200
    company = comp_resp.json()
    company_id = company["id"]

    # =========================================================================
    # Step 2: Bridge Heartbeat & Status Check
    # =========================================================================
    hb_resp = client.post(
        "/api/v1/bridge/heartbeat",
        json={
            "bridge_client_id": "BR-TEST-E2E",
            "status": "ONLINE",
            "tally_status": {"is_online": True, "host": "127.0.0.1", "port": 9000},
        },
        headers=AUTH_HEADERS,
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["status"] == "acknowledged"

    # =========================================================================
    # Step 3: Document Ingestion (Phase 3B)
    # =========================================================================
    invoice_content = (
        b"TAX INVOICE\n"
        b"Vendor: Acme Steel Corp\n"
        b"GSTIN: 27ABCDE1234F1Z5\n"
        b"Invoice No: INV-2026-999\n"
        b"Date: 2026-03-15\n"
        b"Taxable Amount: 10000.00\n"
        b"CGST (9%): 900.00\n"
        b"SGST (9%): 900.00\n"
        b"Total: 11800.00\n"
    )

    upload_resp = client.post(
        "/api/v1/documents/upload",
        data={"company_id": company_id},
        files={"file": ("tax_invoice_999.txt", io.BytesIO(invoice_content), "text/plain")},
    )
    assert upload_resp.status_code == 201
    doc_data = upload_resp.json()
    assert doc_data["status"] == "RECEIVED"
    assert doc_data["is_duplicate"] is False
    assert len(doc_data["sha256_checksum"]) == 64
    document_id = doc_data["id"]

    # Duplicate check verification: Uploading identical file must flag duplicate
    dup_resp = client.post(
        "/api/v1/documents/upload",
        data={"company_id": company_id},
        files={"file": ("tax_invoice_999.txt", io.BytesIO(invoice_content), "text/plain")},
    )
    assert dup_resp.status_code == 201
    assert dup_resp.json()["is_duplicate"] is True

    # =========================================================================
    # Step 4: AI Extraction (Phase 3C)
    # =========================================================================
    extract_resp = client.post(f"/api/v1/documents/{document_id}/extract")
    assert extract_resp.status_code == 200
    extract_data = extract_resp.json()
    assert extract_data["status"] == "EXTRACTED"
    assert extract_data["ai_provider"] in ["GeminiProvider", "gemini"]
    extracted = extract_data["extracted_data"]
    assert extracted["total_amount"] > 0
    assert extracted["vendor_name"] is not None

    # Check that Document status advanced to EXTRACTED
    docs_list = client.get(f"/api/v1/documents?company_id={company_id}").json()
    active_doc = next(d for d in docs_list if d["id"] == document_id)
    assert active_doc["status"] == "EXTRACTED"

    # =========================================================================
    # Step 5: Accounting Proposal Generation & Validation (Phase 3D, 3E, 3F)
    # =========================================================================
    prop_resp = client.post(f"/api/v1/proposals/generate/{document_id}")
    assert prop_resp.status_code == 201
    prop_data = prop_resp.json()
    proposal_id = prop_data["id"]
    assert prop_data["status"] == "PENDING_APPROVAL"
    assert prop_data["voucher_type"] == "Purchase"
    assert len(prop_data["lines"]) >= 2

    # Verify deterministic validation rules passed
    validations = prop_data["validations"]
    assert len(validations) >= 3
    for v in validations:
        assert v["is_passed"] is True, f"Validation failed: {v['rule_code']} - {v['message']}"

    # Verify Document status advanced to PROPOSED
    docs_list = client.get(f"/api/v1/documents?company_id={company_id}").json()
    active_doc = next(d for d in docs_list if d["id"] == document_id)
    assert active_doc["status"] == "PROPOSED"

    # =========================================================================
    # Step 6: Human Approval & Posting Job Creation (Phase 3G, 3H)
    # =========================================================================
    appr_resp = client.post(
        f"/api/v1/proposals/{proposal_id}/approve",
        json={
            "decision": "APPROVED",
            "comments": "Audited and verified against GST Portal",
            "authority_context": "FINANCE_HEAD",
            "approval_signature": "SIG-FH-001-APPROVED",
        },
    )
    assert appr_resp.status_code == 200
    appr_data = appr_resp.json()
    assert appr_data["status"] == "APPROVED"
    assert appr_data["decision"] == "APPROVED"
    assert appr_data["transaction_id"] is not None
    assert appr_data["posting_job_id"] is not None
    posting_job_id = appr_data["posting_job_id"]

    # Verify Document status advanced to APPROVED
    docs_list = client.get(f"/api/v1/documents?company_id={company_id}").json()
    active_doc = next(d for d in docs_list if d["id"] == document_id)
    assert active_doc["status"] == "APPROVED"

    # =========================================================================
    # Step 7: Bridge Polls Pending Jobs (Phase 3H -> 3I)
    # =========================================================================
    poll_resp = client.get("/api/v1/bridge/jobs/pending", headers=AUTH_HEADERS)
    assert poll_resp.status_code == 200
    jobs = poll_resp.json()["jobs"]
    matching_job = next((j for j in jobs if j["job_id"] == posting_job_id), None)
    assert matching_job is not None
    assert matching_job["job_type"] == "POSTING"
    assert "company_ref" in matching_job["payload"]
    assert "lines" in matching_job["payload"]

    # =========================================================================
    # Step 8: Bridge Reports Posting Attempt (Phase 3I)
    # =========================================================================
    attempt_resp = client.post(
        f"/api/v1/bridge/jobs/{posting_job_id}/attempts",
        json={
            "success": True,
            "voucher_guid": "TALLY-VCH-GUID-9999",
            "voucher_number": "PUR/2026/0001",
            "master_id": 1001,
            "status_code": 200,
            "raw_response": "<RESPONSE><STATUS>1</STATUS><VOUCHERNUMBER>PUR/2026/0001</VOUCHERNUMBER></RESPONSE>",
        },
        headers=AUTH_HEADERS,
    )
    assert attempt_resp.status_code == 200
    assert attempt_resp.json()["is_success"] is True

    # Verify Document status advanced to POSTED
    docs_list = client.get(f"/api/v1/documents?company_id={company_id}").json()
    active_doc = next(d for d in docs_list if d["id"] == document_id)
    assert active_doc["status"] == "POSTED"

    # =========================================================================
    # Step 9: Bridge Reports Read-Back Verification (Phase 3J)
    # =========================================================================
    verify_resp = client.post(
        f"/api/v1/bridge/jobs/{posting_job_id}/verification",
        json={
            "is_verified": True,
            "status": "VERIFIED",
            "actual_voucher_number": "PUR/2026/0001",
            "actual_guid": "TALLY-VCH-GUID-9999",
            "actual_amount": prop_data["total_amount"],
            "raw_payload": {"reconciled": True},
        },
        headers=AUTH_HEADERS,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["is_verified"] is True

    # Verify Document status advanced to VERIFIED
    docs_list = client.get(f"/api/v1/documents?company_id={company_id}").json()
    active_doc = next(d for d in docs_list if d["id"] == document_id)
    assert active_doc["status"] == "VERIFIED"

    # =========================================================================
    # Step 10: Immutable Audit Trail Proof (Phase 3K)
    # =========================================================================
    audit_resp = client.get(f"/api/v1/bridge/audit/events?company_id={company_id}")
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    actions = [e["action"] for e in events]

    assert "PROPOSAL_APPROVED" in actions
    assert "VOUCHER_POSTED_TO_TALLY" in actions
    assert "VOUCHER_VERIFIED_READ_BACK" in actions

    # Verify queue is drained of completed job
    remaining_jobs = client.get("/api/v1/bridge/jobs/pending", headers=AUTH_HEADERS).json()["jobs"]
    assert not any(j["job_id"] == posting_job_id for j in remaining_jobs)
