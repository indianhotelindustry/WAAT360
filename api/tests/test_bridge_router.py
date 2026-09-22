from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

AUTH_HEADERS = {
    "X-Bridge-Client-Id": "BR-TEST-001",
    "X-Bridge-Key": "test-key-123",
}


def test_bridge_heartbeat_unauthorized():
    # Missing headers should fail with 401
    resp = client.post("/api/v1/bridge/heartbeat", json={"bridge_client_id": "BR-TEST-001"})
    assert resp.status_code == 401


def test_bridge_heartbeat_authorized():
    payload = {
        "bridge_client_id": "BR-TEST-001",
        "status": "ONLINE",
        "tally_status": {"is_online": True, "version": "TallyPrime 7.0"},
    }
    resp = client.post("/api/v1/bridge/heartbeat", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "acknowledged"
    assert data["client_id"] == "BR-TEST-001"


def test_bridge_report_companies():
    payload = {
        "companies": [
            {"name": "Acme Holdings", "guid": "G-1", "is_active": True},
            {"name": "Beta Labs", "guid": "G-2", "is_active": True},
        ]
    }
    resp = client.post("/api/v1/bridge/companies", json=payload, headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["companies_recorded"] == 2

    # Verify retrieval
    get_resp = client.get("/api/v1/bridge/companies", headers=AUTH_HEADERS)
    assert get_resp.status_code == 200
    names = [c["name"] for c in get_resp.json()["companies"]]
    assert "Acme Holdings" in names
    assert "Beta Labs" in names


def test_bridge_poll_pending_jobs():
    resp = client.get("/api/v1/bridge/jobs/pending", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "jobs" in resp.json()


def test_bridge_record_attempt_and_verification():
    attempt_payload = {
        "success": True,
        "voucher_number": "VCH-9901",
        "voucher_guid": "G-9901",
        "status_code": 200,
    }
    resp1 = client.post(
        "/api/v1/bridge/jobs/JOB-100/attempts",
        json=attempt_payload,
        headers=AUTH_HEADERS,
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "recorded"
    assert resp1.json()["is_success"] is True

    verif_payload = {
        "is_verified": True,
        "status": "VERIFIED",
        "actual_voucher_number": "VCH-9901",
        "actual_guid": "G-9901",
    }
    resp2 = client.post(
        "/api/v1/bridge/jobs/JOB-100/verification",
        json=verif_payload,
        headers=AUTH_HEADERS,
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "recorded"
    assert resp2.json()["is_verified"] is True
