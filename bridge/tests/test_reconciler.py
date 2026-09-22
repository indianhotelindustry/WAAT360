from unittest.mock import MagicMock

import pytest

from src.adapters.base import TallyAdapter
from src.engine.reconciler import PostingReconciler
from src.models.domain import (
    VerificationEvidence,
    VoucherResult,
)
from src.store.local_store import BridgeLocalStore


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=TallyAdapter)
    return adapter


@pytest.fixture
def in_memory_store():
    return BridgeLocalStore(db_path=":memory:")


def test_reconciler_post_and_verify_success(mock_adapter, in_memory_store):
    mock_adapter.verify_transaction.side_effect = [
        # First call (pre-check): not found
        VerificationEvidence(is_verified=False, status="NOT_FOUND"),
        # Second call (post-readback): verified
        VerificationEvidence(
            is_verified=True,
            status="VERIFIED",
            actual_voucher_number="VCH-101",
            actual_guid="G-101",
        ),
    ]
    mock_adapter.create_voucher.return_value = VoucherResult(
        success=True,
        voucher_number="VCH-101",
        voucher_guid="G-101",
    )

    reconciler = PostingReconciler(adapter=mock_adapter, store=in_memory_store)

    job = {
        "job_id": "J1",
        "correlation_id": "C1",
        "payload": {
            "company_ref": {"company_name": "Test Co"},
            "voucher_type": "Purchase",
            "voucher_date": "2026-09-22",
            "reference_number": "INV-001",
            "lines": [{"ledger_name": "Purchases", "amount": 100.0, "is_debit": True}],
        },
    }

    res, evidence = reconciler.execute_posting_job(job)
    assert res.success is True
    assert evidence.is_verified is True
    assert evidence.actual_voucher_number == "VCH-101"

    # Verify store records status
    history = in_memory_store.get_posting_history("C1")
    assert history["status"] == "COMPLETED"
    assert history["voucher_number"] == "VCH-101"


def test_reconciler_prevents_duplicate_on_existing_tally_voucher(mock_adapter, in_memory_store):
    """
    Simulate scenario where previous attempt succeeded in Tally, but client never received ack.
    On retry, reconciler detects existence in Tally and does NOT call create_voucher.
    """
    # Pre-check immediately finds the voucher in Tally
    mock_adapter.verify_transaction.return_value = VerificationEvidence(
        is_verified=True,
        status="VERIFIED",
        actual_voucher_number="VCH-EXISTING",
        actual_guid="G-EXISTING",
    )

    reconciler = PostingReconciler(adapter=mock_adapter, store=in_memory_store)

    job = {
        "job_id": "J2",
        "correlation_id": "C2",
        "payload": {
            "company_ref": {"company_name": "Test Co"},
            "voucher_type": "Purchase",
            "voucher_date": "2026-09-22",
            "reference_number": "INV-ALREADY-CREATED",
            "lines": [{"ledger_name": "Purchases", "amount": 200.0, "is_debit": True}],
        },
    }

    res, evidence = reconciler.execute_posting_job(job)
    assert res.success is True
    assert res.voucher_number == "VCH-EXISTING"
    # Ensure create_voucher was NEVER called again!
    mock_adapter.create_voucher.assert_not_called()


def test_reconciler_reconciles_after_network_timeout(mock_adapter, in_memory_store):
    """
    Posting call raises an error or fails, but post-check verifies the voucher did reach Tally!
    Reconciler marks job as COMPLETED instead of failing or blindly retrying.
    """
    mock_adapter.verify_transaction.side_effect = [
        # Pre-check: not found yet
        VerificationEvidence(is_verified=False, status="NOT_FOUND"),
        # Post-check after failed post: found!
        VerificationEvidence(
            is_verified=True,
            status="VERIFIED",
            actual_voucher_number="VCH-SAVED-ANYWAY",
        ),
    ]
    # create_voucher returns failure (e.g. socket timeout after Tally processed)
    mock_adapter.create_voucher.return_value = VoucherResult(
        success=False,
        error_message="Read timed out",
    )

    reconciler = PostingReconciler(adapter=mock_adapter, store=in_memory_store)

    job = {
        "job_id": "J3",
        "correlation_id": "C3",
        "payload": {
            "company_ref": {"company_name": "Test Co"},
            "voucher_type": "Purchase",
            "voucher_date": "2026-09-22",
            "reference_number": "INV-TIMEOUT",
            "lines": [{"ledger_name": "Purchases", "amount": 300.0, "is_debit": True}],
        },
    }

    res, evidence = reconciler.execute_posting_job(job)
    assert res.success is True
    assert evidence.is_verified is True
    assert evidence.actual_voucher_number == "VCH-SAVED-ANYWAY"
