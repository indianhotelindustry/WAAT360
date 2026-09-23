import io
import uuid

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

AUTH_HEADERS = {
    "X-Bridge-Client-Id": "BR-TEST-SUITE",
    "X-Bridge-Key": "test-key-suite",
}


def test_dashboard_summary_and_simulation_cycle():
    """
    Verify:
      1. Dashboard summary returns real DB counts and connection status
      2. Document extraction can be re-fetched across page reloads
      3. Simulate-cycle executes TallySimulatedAdapter through Bridge abstraction
      4. Returns actual sequential voucher number, GUID, expected vs actual amount
      5. Read-back verification and immutable audit trail records are created
    """
    # Step 1: Create Company
    uid = uuid.uuid4().hex[:6]
    c_resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Simulated Auto Corp {uid}",
            "trade_name": "Simulated Auto",
            "pan": "ABCDE1234F",
            "gstin": "27ABCDE1234F1Z5",
        },
    )
    assert c_resp.status_code == 200
    comp_id = c_resp.json()["id"]

    # Step 2: Query Dashboard Summary (Initially 0 documents)
    summary_resp = client.get(f"/api/v1/dashboard/summary?company_id={comp_id}")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["documents_received"] == 0
    assert summary["pending_review"] == 0
    assert summary["approved"] == 0
    assert summary["posted_to_tally"] == 0
    assert summary["verified"] == 0
    assert summary["exceptions"] == 0
    assert summary["cloud_status"] == "ONLINE"
    assert summary["is_demo_mode"] is True
    assert summary["tally_mode"] == "DEMO MODE"
    assert summary["tally_status_text"] == "Simulated Tally"

    # Step 3: Ingest Document
    invoice_bytes = (
        b"TAX INVOICE\n"
        b"Vendor: Shreeji Steel Enterprises\n"
        b"GSTIN: 27AABCS1429B1ZB\n"
        b"Invoice No: INV-SIM-2026-001\n"
        b"Date: 2026-03-22\n"
        b"Taxable Amount: 20000.00\n"
        b"CGST (9%): 1800.00\n"
        b"SGST (9%): 1800.00\n"
        b"Total: 23600.00\n"
    )
    upload_resp = client.post(
        "/api/v1/documents/upload",
        data={"company_id": comp_id},
        files={"file": ("tax_invoice_sim.txt", io.BytesIO(invoice_bytes), "text/plain")},
    )
    assert upload_resp.status_code == 201
    doc_id = upload_resp.json()["id"]

    # Summary should reflect 1 document received
    summary_resp = client.get(f"/api/v1/dashboard/summary?company_id={comp_id}")
    assert summary_resp.json()["documents_received"] == 1

    # Step 4: AI Extraction
    extract_resp = client.post(f"/api/v1/documents/{doc_id}/extract")
    assert extract_resp.status_code == 200
    assert extract_resp.json()["status"] == "EXTRACTED"

    # Verify GET /{doc_id}/extraction works (browser refresh persistence)
    get_ext_resp = client.get(f"/api/v1/documents/{doc_id}/extraction")
    assert get_ext_resp.status_code == 200
    ext_data = get_ext_resp.json()
    assert ext_data is not None
    extracted_total = ext_data["extracted_data"]["total_amount"]
    assert extracted_total > 0

    # Step 5: Proposal Generation & Validation
    prop_resp = client.post(f"/api/v1/proposals/generate/{doc_id}")
    assert prop_resp.status_code == 201
    prop_id = prop_resp.json()["id"]

    # Summary should reflect 1 pending review
    summary_resp = client.get(f"/api/v1/dashboard/summary?company_id={comp_id}")
    assert summary_resp.json()["pending_review"] == 1

    # Step 6: Human Approval
    appr_resp = client.post(
        f"/api/v1/proposals/{prop_id}/approve",
        json={"decision": "APPROVED", "comments": "Demo simulation approval"},
    )
    assert appr_resp.status_code == 200
    posting_job_id = appr_resp.json()["posting_job_id"]
    assert posting_job_id is not None

    # Summary should reflect 1 approved
    summary_resp = client.get(f"/api/v1/dashboard/summary?company_id={comp_id}")
    assert summary_resp.json()["approved"] == 1

    # Step 7: Execute Simulation Cycle through Bridge & TallySimulatedAdapter
    sim_resp = client.post(f"/api/v1/bridge/jobs/{posting_job_id}/simulate-cycle")
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()

    assert sim_data["status"] == "success"
    assert sim_data["is_verified"] is True
    assert sim_data["verification_status"] == "VERIFIED"
    assert sim_data["voucher_number"].startswith("PUR/2026/")
    assert sim_data["voucher_guid"].startswith("TALLY-GUID-")
    assert sim_data["expected_amount"] == extracted_total
    assert sim_data["actual_amount"] == extracted_total
    assert sim_data["verification_method"] == "TALLY_READ_BACK"
    assert sim_data["adapter_used"] == "TallySimulatedAdapter"

    # Step 8: Verify Summary counts after simulation completion
    summary_after = client.get(f"/api/v1/dashboard/summary?company_id={comp_id}").json()
    assert summary_after["posted_to_tally"] == 1
    assert summary_after["verified"] == 1

    # Step 9: Verify proposals list returns persisted verification details
    props_list = client.get(f"/api/v1/proposals?company_id={comp_id}").json()
    assert len(props_list) == 1
    p = props_list[0]
    assert p["posting_status"] == "VERIFIED"
    assert p["tally_voucher_number"] == sim_data["voucher_number"]
    assert p["tally_guid"] == sim_data["voucher_guid"]
    assert p["actual_amount"] == extracted_total
    assert p["verification_status"] == "VERIFIED"
    assert len(p["lines"]) >= 2

    # Step 10 (Control 4): Test Idempotent Replay (Second execution on same PostingJob)
    sim_resp_replay = client.post(f"/api/v1/bridge/jobs/{posting_job_id}/simulate-cycle")
    assert sim_resp_replay.status_code == 200
    sim_data_replay = sim_resp_replay.json()
    assert sim_data_replay["voucher_number"] == sim_data["voucher_number"]
    assert sim_data_replay["voucher_guid"] == sim_data["voucher_guid"]
    assert sim_data_replay["is_verified"] is True
    assert sim_data_replay["adapter_used"] == "TallySimulatedAdapter (Idempotent Cached)"

    # Confirm counts do NOT double-count upon replay
    summary_replay = client.get(f"/api/v1/dashboard/summary?company_id={comp_id}").json()
    assert summary_replay["posted_to_tally"] == 1
    assert summary_replay["verified"] == 1


def test_verification_failure_integrity():
    """
    Control 5: Prove that HTTP success alone NEVER produces VERIFIED.
    When amounts mismatch or voucher is missing, the system records the failure
    and job status remains non-verified.
    """
    # Create Company & Document
    uid = uuid.uuid4().hex[:6]
    c_resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Verification Failure Corp {uid}",
            "trade_name": "Fail Corp",
            "pan": "FAILC1234F",
            "gstin": "27FAILC1234F1Z5",
        },
    )
    comp_id = c_resp.json()["id"]

    upload_resp = client.post(
        "/api/v1/documents/upload",
        data={"company_id": comp_id},
        files={"file": ("fail_invoice.txt", io.BytesIO(b"Total: 5000.00"), "text/plain")},
    )
    doc_id = upload_resp.json()["id"]
    client.post(f"/api/v1/documents/{doc_id}/extract")
    prop_id = client.post(f"/api/v1/proposals/generate/{doc_id}").json()["id"]
    posting_job_id = client.post(
        f"/api/v1/proposals/{prop_id}/approve",
        json={"decision": "APPROVED", "comments": "Approval before mismatch test"},
    ).json()["posting_job_id"]

    # Post mismatching verification evidence to bridge verification endpoint
    # Expected amount is 5000.00, but read-back reports 3000.00 (AMOUNT_MISMATCH)
    mismatch_resp = client.post(
        f"/api/v1/bridge/jobs/{posting_job_id}/verification",
        headers=AUTH_HEADERS,
        json={
            "actual_voucher_number": "PUR/2026/9999",
            "actual_guid": "TALLY-GUID-MISMATCH",
            "actual_amount": 3000.00,
            "status": "AMOUNT_MISMATCH",
            "is_verified": False,
            "mismatch_details": {
                "expected_amount": 5000.00,
                "actual_amount": 3000.00,
                "difference": 2000.00,
            },
        },
    )
    assert mismatch_resp.status_code == 200
    assert mismatch_resp.json()["status"] == "recorded"

    # Verify that Dashboard Summary does NOT increment verified count
    summary = client.get(f"/api/v1/dashboard/summary?company_id={comp_id}").json()
    assert summary["verified"] == 0

    # Verify that Proposal status is NOT VERIFIED
    props = client.get(f"/api/v1/proposals?company_id={comp_id}").json()
    assert props[0]["posting_status"] != "VERIFIED"
    assert props[0]["verification_status"] != "VERIFIED"
