import os
import tempfile

import pytest

from src.store.local_store import BridgeLocalStore


@pytest.fixture
def temp_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = BridgeLocalStore(db_path=path)
    yield store
    try:
        os.remove(path)
    except Exception:
        pass


def test_enqueue_and_get_pending_jobs(temp_store):
    payload = {"company_ref": {"company_name": "Test Co"}, "voucher_type": "Purchase"}
    ok = temp_store.enqueue_job(
        job_id="JOB-001",
        correlation_id="CORR-001",
        job_type="POSTING",
        payload=payload,
    )
    assert ok is True

    pending = temp_store.get_pending_jobs()
    assert len(pending) == 1
    assert pending[0]["job_id"] == "JOB-001"
    assert pending[0]["status"] == "PENDING"
    assert pending[0]["payload"]["voucher_type"] == "Purchase"


def test_update_job_status_and_retry(temp_store):
    temp_store.enqueue_job("JOB-002", "CORR-002", "POSTING", {})
    temp_store.update_job_status(
        "JOB-002", status="FAILED", error_message="Timeout", increment_retry=True
    )

    with temp_store._get_connection() as conn:
        row = conn.execute(
            "SELECT status, retry_count, error_message FROM jobs WHERE job_id = 'JOB-002'"
        ).fetchone()
        assert row["status"] == "FAILED"
        assert row["retry_count"] == 1
        assert row["error_message"] == "Timeout"


def test_idempotency_posting_history(temp_store):
    temp_store.record_posting_history(
        correlation_id="CORR-IDEM-01",
        voucher_reference="INV-999",
        voucher_number="VCH-123",
        status="COMPLETED",
        result={"guid": "G-123"},
    )

    history = temp_store.get_posting_history("CORR-IDEM-01")
    assert history is not None
    assert history["voucher_number"] == "VCH-123"
    assert history["status"] == "COMPLETED"
    assert history["result"]["guid"] == "G-123"


def test_tally_health_cache(temp_store):
    temp_store.update_tally_health(
        is_online=True,
        version="TallyPrime 7.0",
        response_time_ms=12.5,
        capabilities={"supports_json": True},
    )

    health = temp_store.get_last_tally_health()
    assert health is not None
    assert health["is_online"] is True
    assert health["version"] == "TallyPrime 7.0"
    assert health["capabilities"]["supports_json"] is True
