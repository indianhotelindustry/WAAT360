from datetime import date

from src.adapters.simulated_adapter import TallySimulatedAdapter
from src.models.domain import (
    CreateVoucherCommand,
    TallyCompanyRef,
    VerificationQuery,
    VoucherLineData,
)


def test_simulated_adapter_status_and_discovery():
    adapter = TallySimulatedAdapter()
    status = adapter.get_tally_status()
    assert status.is_online is True
    assert status.host == "127.0.0.1"
    assert status.port == 9000
    assert "Simulated" in status.tally_version

    companies = adapter.get_companies()
    assert len(companies) == 3
    names = [c.name for c in companies]
    assert "Tata Motors Technologies Ltd" in names
    assert "Acme Industrial Technologies Pvt Ltd" in names


def test_simulated_adapter_ledgers_and_parties():
    adapter = TallySimulatedAdapter()
    company_ref = TallyCompanyRef(company_name="Acme Industrial Technologies Pvt Ltd")

    ledgers = adapter.get_ledgers(company_ref)
    assert len(ledgers) >= 10
    ledger_names = [ledger.name for ledger in ledgers]

    assert "Purchase A/c" in ledger_names
    assert "Input CGST 9%" in ledger_names
    assert "Input SGST 9%" in ledger_names

    parties = adapter.get_parties(company_ref)
    assert len(parties) >= 3
    creditors = [p for p in parties if p.party_type == "CREDITOR"]
    assert len(creditors) >= 2


def test_simulated_adapter_create_voucher_and_verify():
    adapter = TallySimulatedAdapter()
    company_ref = TallyCompanyRef(company_name="Acme Industrial Technologies Pvt Ltd")

    cmd = CreateVoucherCommand(
        company_ref=company_ref,
        voucher_type="Purchase",
        voucher_date=date(2026, 9, 22),
        reference_number="BILL-SIM-101",
        narration="Purchase of raw materials",
        lines=[
            VoucherLineData(ledger_name="Purchase A/c", amount=10000.0, is_debit=True),
            VoucherLineData(ledger_name="Input CGST 9%", amount=900.0, is_debit=True),
            VoucherLineData(ledger_name="Input SGST 9%", amount=900.0, is_debit=True),
            VoucherLineData(ledger_name="Shreeji Steel Traders", amount=11800.0, is_debit=False),
        ],
        correlation_id="CORR-SIM-101",
    )

    result = adapter.create_voucher(cmd)
    assert result.success is True
    assert result.voucher_number.startswith("PUR/2026/")
    assert result.voucher_guid is not None

    # Read-back verification
    query = VerificationQuery(
        company_ref=company_ref,
        correlation_id="CORR-SIM-101",
        expected_reference="BILL-SIM-101",
        expected_amount=11800.0,
        voucher_type="Purchase",
    )
    evidence = adapter.verify_transaction(query)
    assert evidence.is_verified is True
    assert evidence.status == "VERIFIED"
    assert evidence.actual_voucher_number == result.voucher_number
    assert evidence.actual_amount == 11800.0


def test_simulated_adapter_idempotency_duplicate_prevention():
    adapter = TallySimulatedAdapter()
    company_ref = TallyCompanyRef(company_name="Acme Industrial Technologies Pvt Ltd")

    cmd = CreateVoucherCommand(
        company_ref=company_ref,
        voucher_type="Purchase",
        voucher_date=date(2026, 9, 22),
        reference_number="BILL-SIM-102",
        lines=[
            VoucherLineData(ledger_name="Purchase A/c", amount=5000.0, is_debit=True),
            VoucherLineData(ledger_name="Shreeji Steel Traders", amount=5000.0, is_debit=False),
        ],
        correlation_id="CORR-SIM-102",
    )

    res1 = adapter.create_voucher(cmd)
    # Immediate retry with same correlation_id
    res2 = adapter.create_voucher(cmd)

    assert res1.voucher_number == res2.voucher_number
    assert res1.voucher_guid == res2.voucher_guid
