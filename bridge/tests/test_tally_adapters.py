from datetime import date
from unittest.mock import patch

import pytest

from src.adapters.factory import get_tally_adapter
from src.adapters.json_adapter import TallyJsonAdapter
from src.adapters.xml_adapter import TallyXmlAdapter
from src.models.domain import (
    CreateVoucherCommand,
    TallyCompanyRef,
    VerificationQuery,
    VoucherLineData,
)


@pytest.fixture
def company_ref():
    return TallyCompanyRef(
        company_name="Acme Corp Ltd",
        tally_guid="GUID-ACME-001",
    )


# =========================================================================
# XML ADAPTER TESTS
# =========================================================================


def test_xml_adapter_get_status_online():
    adapter = TallyXmlAdapter(host="127.0.0.1", port=9000)
    mock_xml = "<ENVELOPE><BODY><DATA><COLLECTION><COMPANY><NAME>Acme Corp Ltd</NAME></COMPANY></COLLECTION></DATA></BODY></ENVELOPE>"

    with patch.object(adapter, "_post_xml", return_value=mock_xml):
        status = adapter.get_tally_status()
        assert status.is_online is True
        assert status.capabilities.supports_xml is True
        assert status.capabilities.supports_json is False


def test_xml_adapter_get_companies(company_ref):
    adapter = TallyXmlAdapter()
    mock_xml = """<ENVELOPE>
  <BODY>
    <EXPORTDATA>
      <COMPANY><NAME>Acme Corp Ltd</NAME><GUID>GUID-ACME-001</GUID></COMPANY>
      <COMPANY><NAME>Beta Industries</NAME><GUID>GUID-BETA-002</GUID></COMPANY>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""

    with patch.object(adapter, "_post_xml", return_value=mock_xml):
        companies = adapter.get_companies()
        assert len(companies) == 2
        assert companies[0].name == "Acme Corp Ltd"
        assert companies[0].guid == "GUID-ACME-001"
        assert companies[1].name == "Beta Industries"


def test_xml_adapter_get_ledgers(company_ref):
    adapter = TallyXmlAdapter()
    mock_xml = """<ENVELOPE>
  <BODY>
    <EXPORTDATA>
      <LEDGER NAME="Supplier ABC"><PARENT>Sundry Creditors</PARENT><OPENINGBALANCE>-5000.00</OPENINGBALANCE></LEDGER>
      <LEDGER NAME="Customer XYZ"><PARENT>Sundry Debtors</PARENT><OPENINGBALANCE>12000.00</OPENINGBALANCE></LEDGER>
      <LEDGER NAME="Purchase A/c"><PARENT>Purchase Accounts</PARENT><OPENINGBALANCE>0</OPENINGBALANCE></LEDGER>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""

    with patch.object(adapter, "_post_xml", return_value=mock_xml):
        ledgers = adapter.get_ledgers(company_ref)
        assert len(ledgers) == 3
        assert ledgers[0].name == "Supplier ABC"
        assert ledgers[0].parent_group == "Sundry Creditors"

        parties = adapter.get_parties(company_ref)
        assert len(parties) == 2
        types = [p.party_type for p in parties]
        assert "CREDITOR" in types
        assert "DEBTOR" in types


def test_xml_adapter_create_voucher_success(company_ref):
    adapter = TallyXmlAdapter()
    cmd = CreateVoucherCommand(
        company_ref=company_ref,
        voucher_type="Purchase",
        voucher_date=date(2026, 9, 22),
        reference_number="BILL-9901",
        narration="Test Purchase",
        lines=[
            VoucherLineData(ledger_name="Purchase A/c", amount=10000.0, is_debit=True),
            VoucherLineData(ledger_name="Supplier ABC", amount=10000.0, is_debit=False),
        ],
        correlation_id="CORR-XML-001",
    )

    mock_resp = """<RESPONSE>
  <CREATED>1</CREATED>
  <ALTERED>0</ALTERED>
  <DELETED>0</DELETED>
  <ERRORS>0</ERRORS>
  <LASTVCHID>VCH-2026-9901</LASTVCHID>
</RESPONSE>"""

    with patch.object(adapter, "_post_xml", return_value=mock_resp) as mock_post:
        res = adapter.create_voucher(cmd)
        assert res.success is True
        assert res.voucher_number == "VCH-2026-9901"
        # Verify SVCURRENTCOMPANY was injected
        sent_xml = mock_post.call_args[0][0]
        assert "<SVCURRENTCOMPANY>Acme Corp Ltd</SVCURRENTCOMPANY>" in sent_xml
        assert "<LEDGERNAME>Purchase A/c</LEDGERNAME>" in sent_xml


def test_xml_adapter_verify_transaction(company_ref):
    adapter = TallyXmlAdapter()
    query = VerificationQuery(
        company_ref=company_ref,
        correlation_id="CORR-XML-001",
        expected_reference="BILL-9901",
        expected_amount=10000.0,
        voucher_type="Purchase",
    )

    mock_vch_xml = """<ENVELOPE>
  <BODY>
    <EXPORTDATA>
      <VOUCHER>
        <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
        <VOUCHERNUMBER>VCH-2026-9901</VOUCHERNUMBER>
        <REFERENCE>BILL-9901</REFERENCE>
        <GUID>GUID-VCH-9901</GUID>
      </VOUCHER>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""

    with patch.object(adapter, "_post_xml", return_value=mock_vch_xml):
        evidence = adapter.verify_transaction(query)
        assert evidence.is_verified is True
        assert evidence.status == "VERIFIED"
        assert evidence.actual_voucher_number == "VCH-2026-9901"
        assert evidence.actual_guid == "GUID-VCH-9901"


# =========================================================================
# JSON ADAPTER TESTS
# =========================================================================


def test_json_adapter_get_companies(company_ref):
    adapter = TallyJsonAdapter()
    mock_json = {
        "status": "success",
        "data": [
            {"name": "Acme Corp Ltd", "guid": "G1", "is_active": True},
            {"name": "Delta Services", "guid": "G2", "is_active": True},
        ],
    }

    with patch.object(adapter, "_post_json", return_value=mock_json):
        companies = adapter.get_companies()
        assert len(companies) == 2
        assert companies[0].name == "Acme Corp Ltd"
        assert companies[1].name == "Delta Services"


def test_json_adapter_create_voucher(company_ref):
    adapter = TallyJsonAdapter()
    cmd = CreateVoucherCommand(
        company_ref=company_ref,
        voucher_type="Purchase",
        voucher_date=date(2026, 9, 22),
        reference_number="INV-JSON-55",
        lines=[
            VoucherLineData(ledger_name="Purchase A/c", amount=5000.0, is_debit=True),
            VoucherLineData(ledger_name="Vendor 1", amount=5000.0, is_debit=False),
        ],
        correlation_id="CORR-JSON-001",
    )

    mock_resp = {
        "status": "success",
        "data": {
            "voucher_number": "VCH-JSON-55",
            "guid": "TALLY-GUID-55",
            "master_id": 1204,
        },
    }

    with patch.object(adapter, "_post_json", return_value=mock_resp) as mock_post:
        res = adapter.create_voucher(cmd)
        assert res.success is True
        assert res.voucher_number == "VCH-JSON-55"
        # Verify svCurrentCompany explicit binding
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["company_name"] == "Acme Corp Ltd"
        payload_sent = mock_post.call_args[0][1]
        assert payload_sent["svCurrentCompany"] == "Acme Corp Ltd"


def test_adapter_factory_fallback():
    # If JSON probing fails, factory falls back to XML adapter
    with patch(
        "src.adapters.json_adapter.TallyJsonAdapter.get_tally_status",
        side_effect=Exception("No JSON"),
    ):
        adapter = get_tally_adapter(prefer_json=True)
        assert isinstance(adapter, TallyXmlAdapter)
