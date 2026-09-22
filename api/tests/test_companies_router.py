import uuid

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

AUTH_HEADERS = {
    "X-Bridge-Client-Id": "BR-TEST-001",
    "X-Bridge-Key": "test-key-123",
}


def test_company_lifecycle_and_tally_mapping():
    unique_suffix = uuid.uuid4().hex[:6]
    test_company_name = f"Acme Global {unique_suffix} Pvt Ltd"
    test_tally_name = f"Acme Live Tally {unique_suffix}"

    # 1. Create a WAAST360 Company
    create_payload = {
        "legal_name": test_company_name,
        "trade_name": "Acme Global",
        "pan": "ABCDE1234F",
        "gstin": "27ABCDE1234F1Z5",
        "currency": "INR",
    }
    create_resp = client.post("/api/v1/companies", json=create_payload)
    assert create_resp.status_code == 200
    company_data = create_resp.json()
    assert company_data["legal_name"] == test_company_name
    company_id = company_data["id"]

    # 2. Bridge reports discovered companies from Tally
    bridge_payload = {
        "companies": [
            {
                "name": test_tally_name,
                "guid": f"TALLY-GUID-{unique_suffix}",
                "financial_year_from": "2024-2025",
                "books_from": "2024-04-01",
                "is_active": True,
            }
        ]
    }
    bridge_resp = client.post("/api/v1/bridge/companies", json=bridge_payload, headers=AUTH_HEADERS)
    assert bridge_resp.status_code == 200
    assert bridge_resp.json()["status"] == "synchronized"

    # 3. Query discovered Tally companies
    tally_comps_resp = client.get("/api/v1/tally-companies")
    assert tally_comps_resp.status_code == 200
    tally_comps = tally_comps_resp.json()
    matching_tally = next((c for c in tally_comps if c["company_name"] == test_tally_name), None)
    assert matching_tally is not None
    assert matching_tally["status"] == "DISCOVERED"
    tally_comp_id = matching_tally["id"]

    # 4. Map the discovered Tally Company to the WAAST360 Company
    map_resp = client.post(f"/api/v1/companies/{company_id}/map-tally/{tally_comp_id}")
    assert map_resp.status_code == 200
    map_data = map_resp.json()
    assert map_data["status"] == "mapped"
    assert map_data["company_id"] == company_id
    assert map_data["tally_company_id"] == tally_comp_id

    # 5. Verify mapped status in company listing
    list_resp = client.get("/api/v1/companies")
    assert list_resp.status_code == 200
    companies = list_resp.json()
    updated_company = next((c for c in companies if c["id"] == company_id), None)
    assert updated_company is not None
    assert updated_company["mapped_tally_company_id"] == tally_comp_id
    assert updated_company["mapped_tally_company_name"] == test_tally_name
