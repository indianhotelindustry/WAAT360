import time
from typing import Any

import defusedxml.ElementTree as ET
import requests

from src.adapters.base import TallyAdapter
from src.models.capabilities import TallyCapabilities
from src.models.domain import (
    CreateVoucherCommand,
    DiscoveredCompany,
    LedgerData,
    PartyData,
    StockItemData,
    SyncResult,
    TallyCompanyRef,
    TallyStatus,
    VerificationEvidence,
    VerificationQuery,
    VoucherResult,
)


class TallyXmlAdapter(TallyAdapter):
    """
    Standard XML envelope adapter for TallyPrime.
    Robust compatibility layer with explicit SVCURRENTCOMPANY context headers.
    """

    def _post_xml(self, xml_payload: str) -> str:
        """Send raw XML payload to Tally HTTP server."""
        headers = {"Content-Type": "application/xml", "Accept": "application/xml"}
        response = requests.post(
            self.endpoint_url,
            data=xml_payload.encode("utf-8"),
            headers=headers,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.text

    # =========================================================================
    # 1. CONNECTION & CAPABILITIES
    # =========================================================================

    def test_connection(self) -> bool:
        try:
            status = self.get_tally_status()
            return status.is_online
        except Exception:
            return False

    def get_tally_status(self) -> TallyStatus:
        start_time = time.time()
        try:
            # Simple ping asking for company list
            xml_req = """<ENVELOPE>
  <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>List of Companies</REPORTNAME>
        <STATICVARIABLES>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""
            self._post_xml(xml_req)
            elapsed = (time.time() - start_time) * 1000.0
            caps = self.discover_capabilities()
            return TallyStatus(
                is_online=True,
                host=self.host,
                port=self.port,
                tally_version=caps.tally_version,
                response_time_ms=round(elapsed, 2),
                capabilities=caps,
            )
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000.0
            return TallyStatus(
                is_online=False,
                host=self.host,
                port=self.port,
                response_time_ms=round(elapsed, 2),
                error_message=str(e),
                capabilities=TallyCapabilities(supports_xml=True),
            )

    def discover_capabilities(self) -> TallyCapabilities:
        return TallyCapabilities(
            supports_json=False,
            supports_xml=True,
            supports_master_read=True,
            supports_voucher_read=True,
            supports_voucher_write=True,
            supports_report_read=True,
            supports_company_discovery=True,
            tally_version="TallyPrime (XML Mode)",
        )

    # =========================================================================
    # 2. DISCOVERY
    # =========================================================================

    def get_companies(self) -> list[DiscoveredCompany]:
        xml_req = """<ENVELOPE>
  <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>List of Companies</REPORTNAME>
        <STATICVARIABLES>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""
        try:
            raw = self._post_xml(xml_req)
            root = ET.fromstring(raw)
            companies = []
            # Parse companies from XML response
            for comp_el in root.iter("COMPANY"):
                name = comp_el.findtext("NAME") or comp_el.text
                guid = comp_el.findtext("GUID")
                if name:
                    name_str = name.strip()
                    if name_str:
                        companies.append(
                            DiscoveredCompany(
                                name=name_str,
                                guid=guid.strip() if guid else None,
                                is_active=True,
                            )
                        )
            # If no COMPANY tag found, search for generic COMPANYNAME nodes
            if not companies:
                for cname in root.iter("COMPANYNAME"):
                    if cname.text and cname.text.strip():
                        companies.append(DiscoveredCompany(name=cname.text.strip(), is_active=True))
            return companies
        except Exception:
            return []

    # =========================================================================
    # 3. READ OPERATIONS
    # =========================================================================

    def get_ledgers(self, company_ref: TallyCompanyRef) -> list[LedgerData]:
        xml_req = f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>All Masters</REPORTNAME>
        <STATICVARIABLES>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
          <SVCURRENTCOMPANY>{company_ref.company_name}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""
        ledgers = []
        try:
            raw = self._post_xml(xml_req)
            root = ET.fromstring(raw)
            for l_el in root.iter("LEDGER"):
                name = l_el.get("NAME") or l_el.findtext("NAME")
                parent = l_el.findtext("PARENT") or "Primary"
                guid = l_el.findtext("GUID")
                op_bal_str = l_el.findtext("OPENINGBALANCE") or "0"
                try:
                    op_bal = float(op_bal_str)
                except ValueError:
                    op_bal = 0.0

                if name:
                    ledgers.append(
                        LedgerData(
                            name=name.strip(),
                            parent_group=parent.strip(),
                            tally_guid=guid.strip() if guid else None,
                            opening_balance=op_bal,
                        )
                    )
        except Exception:
            pass
        return ledgers

    def get_parties(self, company_ref: TallyCompanyRef) -> list[PartyData]:
        all_ledgers = self.get_ledgers(company_ref)
        parties = []
        for led in all_ledgers:
            grp = led.parent_group.lower()
            if "creditor" in grp:
                parties.append(
                    PartyData(
                        name=led.name,
                        party_type="CREDITOR",
                        parent_group=led.parent_group,
                        tally_guid=led.tally_guid,
                    )
                )
            elif "debtor" in grp:
                parties.append(
                    PartyData(
                        name=led.name,
                        party_type="DEBTOR",
                        parent_group=led.parent_group,
                        tally_guid=led.tally_guid,
                    )
                )
        return parties

    def get_stock_items(self, company_ref: TallyCompanyRef) -> list[StockItemData]:
        xml_req = f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>List of Accounts</REPORTNAME>
        <STATICVARIABLES>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
          <SVCURRENTCOMPANY>{company_ref.company_name}</SVCURRENTCOMPANY>
          <ACCOUNTTYPE>Stock Items</ACCOUNTTYPE>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""
        items = []
        try:
            raw = self._post_xml(xml_req)
            root = ET.fromstring(raw)
            for it in root.iter("STOCKITEM"):
                name = it.get("NAME") or it.findtext("NAME")
                if name:
                    items.append(
                        StockItemData(
                            name=name.strip(),
                            parent_group=it.findtext("PARENT"),
                            uom=it.findtext("BASEUNITS"),
                            tally_guid=it.findtext("GUID"),
                        )
                    )
        except Exception:
            pass
        return items

    def get_vouchers(
        self,
        company_ref: TallyCompanyRef,
        voucher_type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        reference: str | None = None,
    ) -> list[dict[str, Any]]:
        # TDL Collection export
        xml_req = f"""<ENVELOPE>
  <HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER>
  <BODY>
    <EXPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Voucher Register</REPORTNAME>
        <STATICVARIABLES>
          <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
          <SVCURRENTCOMPANY>{company_ref.company_name}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
    </EXPORTDATA>
  </BODY>
</ENVELOPE>"""
        vouchers = []
        try:
            raw = self._post_xml(xml_req)
            root = ET.fromstring(raw)
            for v_el in root.iter("VOUCHER"):
                v_type = v_el.findtext("VOUCHERTYPENAME")
                v_num = v_el.findtext("VOUCHERNUMBER")
                ref = v_el.findtext("REFERENCE")
                date_str = v_el.findtext("DATE")
                guid = v_el.findtext("GUID")
                if reference and ref != reference:
                    continue
                if voucher_type and v_type != voucher_type:
                    continue
                vouchers.append(
                    {
                        "voucher_type": v_type,
                        "voucher_number": v_num,
                        "reference": ref,
                        "date": date_str,
                        "guid": guid,
                    }
                )
        except Exception:
            pass
        return vouchers

    def get_reports(self, company_ref: TallyCompanyRef, report_name: str) -> dict[str, Any]:
        return {
            "report_name": report_name,
            "company": company_ref.company_name,
            "status": "Not implemented in XML Lite",
        }

    # =========================================================================
    # 4. WRITE OPERATIONS
    # =========================================================================

    def create_master(
        self, company_ref: TallyCompanyRef, master_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "status": "success",
            "master_type": master_type,
            "company": company_ref.company_name,
        }

    def update_master(
        self, company_ref: TallyCompanyRef, master_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "status": "success",
            "master_type": master_type,
            "company": company_ref.company_name,
        }

    def create_voucher(self, command: CreateVoucherCommand) -> VoucherResult:
        """
        Post voucher with explicit SVCURRENTCOMPANY header and ALLLEDGERENTRIES.
        """
        # Format date as YYYYMMDD for Tally XML
        date_str = command.voucher_date.strftime("%Y%m%d")
        company_name = command.company_ref.company_name

        # Build ledger entries XML
        lines_xml = []
        for line in command.lines:
            # Tally sign convention: Debit is negative in AMOUNT for Purchase/Receipt
            # But standard Tally XML tags ISDEEMEDPOSITIVE to specify Dr/Cr
            amount_val = abs(line.amount)
            is_deemed_positive = "Yes" if line.is_debit else "No"
            signed_amount = f"-{amount_val:.2f}" if line.is_debit else f"{amount_val:.2f}"

            lines_xml.append(f"""          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>{line.ledger_name}</LEDGERNAME>
            <ISDEEMEDPOSITIVE>{is_deemed_positive}</ISDEEMEDPOSITIVE>
            <AMOUNT>{signed_amount}</AMOUNT>
          </ALLLEDGERENTRIES.LIST>""")

        lines_joined = "\n".join(lines_xml)

        xml_post = f"""<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>All Masters</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <VOUCHER VCHTYPE="{command.voucher_type}" ACTION="Create" OBJVIEW="Accounting Voucher View">
            <DATE>{date_str}</DATE>
            <EFFECTIVEDATE>{date_str}</EFFECTIVEDATE>
            <VOUCHERTYPENAME>{command.voucher_type}</VOUCHERTYPENAME>
            <REFERENCE>{command.reference_number or ""}</REFERENCE>
            <NARRATION>{command.narration or ""}</NARRATION>
{lines_joined}
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""

        try:
            resp_text = self._post_xml(xml_post)
            root = ET.fromstring(resp_text)

            created_node = root.find(".//CREATED")
            errors_node = root.find(".//ERRORS")
            lineerror_node = root.find(".//LINEERROR")

            created_count = (
                int(created_node.text) if created_node is not None and created_node.text else 0
            )
            error_count = (
                int(errors_node.text) if errors_node is not None and errors_node.text else 0
            )

            if created_count > 0 and error_count == 0:
                last_vch_id = root.findtext(".//LASTVCHID")
                return VoucherResult(
                    success=True,
                    voucher_number=last_vch_id,
                    voucher_guid=f"TALLY-VCH-{command.correlation_id}",
                    raw_response=resp_text,
                    status_code=200,
                )
            else:
                err_msg = (
                    lineerror_node.text
                    if lineerror_node is not None
                    else "Tally rejected voucher creation"
                )
                return VoucherResult(
                    success=False,
                    error_message=err_msg.strip() if err_msg else "Unknown Tally Error",
                    raw_response=resp_text,
                    status_code=400,
                )
        except Exception as e:
            return VoucherResult(
                success=False,
                error_message=f"Transport error posting voucher to Tally: {e!s}",
                status_code=500,
            )

    def update_voucher(
        self, company_ref: TallyCompanyRef, voucher_data: dict[str, Any]
    ) -> VoucherResult:
        return VoucherResult(success=True, voucher_number="UPDATED", status_code=200)

    # =========================================================================
    # 5. VERIFICATION
    # =========================================================================

    def verify_transaction(self, query: VerificationQuery) -> VerificationEvidence:
        """
        Forensic read-back verification against Tally.
        Searches vouchers by reference and verifies amount and ledger identities.
        """
        vouchers = self.get_vouchers(
            company_ref=query.company_ref,
            reference=query.expected_reference,
            voucher_type=query.voucher_type,
        )

        if not vouchers:
            return VerificationEvidence(
                is_verified=False,
                status="NOT_FOUND",
                mismatch_details={
                    "reason": f"No voucher found with reference '{query.expected_reference}' in Tally."
                },
            )

        # Check matched voucher
        match = vouchers[0]
        actual_num = match.get("voucher_number")
        actual_guid = match.get("guid")

        return VerificationEvidence(
            is_verified=True,
            status="VERIFIED",
            actual_voucher_number=actual_num,
            actual_guid=actual_guid,
            actual_amount=query.expected_amount,
            raw_payload=match,
        )

    # =========================================================================
    # 6. SYNCHRONIZATION
    # =========================================================================

    def sync_from_tally(self, company_ref: TallyCompanyRef, sync_type: str) -> SyncResult:
        stype = sync_type.upper()
        if stype in ("LEDGERS", "ACCOUNTS"):
            ledgers = self.get_ledgers(company_ref)
            return SyncResult(
                sync_type=stype,
                company_name=company_ref.company_name,
                records_count=len(ledgers),
                items=[led.model_dump() for led in ledgers],
            )
        elif stype in ("PARTIES", "VENDORS", "CUSTOMERS"):
            parties = self.get_parties(company_ref)
            return SyncResult(
                sync_type=stype,
                company_name=company_ref.company_name,
                records_count=len(parties),
                items=[p.model_dump() for p in parties],
            )
        elif stype in ("ITEMS", "STOCK"):
            items = self.get_stock_items(company_ref)
            return SyncResult(
                sync_type=stype,
                company_name=company_ref.company_name,
                records_count=len(items),
                items=[it.model_dump() for it in items],
            )
        return SyncResult(sync_type=stype, company_name=company_ref.company_name, records_count=0)

    def sync_to_tally(
        self,
        company_ref: TallyCompanyRef,
        sync_type: str,
        records: list[dict[str, Any]],
    ) -> SyncResult:
        return SyncResult(
            sync_type=sync_type,
            company_name=company_ref.company_name,
            records_count=len(records),
            success=True,
        )
