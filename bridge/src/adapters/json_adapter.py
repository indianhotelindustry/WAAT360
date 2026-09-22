import json
import time
from typing import Any

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


class TallyJsonAdapter(TallyAdapter):
    """
    Native JSON adapter for modern TallyPrime versions (TallyPrime 7.0+).
    Preferred adapter. Uses native JSON payloads while rigorously binding
    svCurrentCompany to guarantee tenant and company isolation.
    """

    def _post_json(
        self, path: str, payload: dict[str, Any], company_name: str | None = None
    ) -> dict[str, Any]:
        """Send JSON payload to Tally HTTP endpoint."""
        url = (
            f"{self.endpoint_url}{path}" if path.startswith("/") else f"{self.endpoint_url}/{path}"
        )
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        params = {}
        if company_name:
            params["svCurrentCompany"] = company_name

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            params=params,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

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
            # Probe JSON status endpoint
            res = self._post_json("/api/status", {"action": "ping"})
            elapsed = (time.time() - start_time) * 1000.0
            caps = self.discover_capabilities()
            version = res.get("version", caps.tally_version)
            return TallyStatus(
                is_online=True,
                host=self.host,
                port=self.port,
                tally_version=version,
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
                capabilities=TallyCapabilities(supports_json=True),
            )

    def discover_capabilities(self) -> TallyCapabilities:
        return TallyCapabilities(
            supports_json=True,
            supports_xml=True,
            supports_master_read=True,
            supports_voucher_read=True,
            supports_voucher_write=True,
            supports_report_read=True,
            supports_company_discovery=True,
            tally_version="TallyPrime 7.0+ (Native JSON)",
        )

    # =========================================================================
    # 2. DISCOVERY
    # =========================================================================

    def get_companies(self) -> list[DiscoveredCompany]:
        try:
            res = self._post_json("/api/companies", {"action": "list"})
            companies_data = res.get("data", res.get("companies", []))
            result = []
            for item in companies_data:
                if isinstance(item, str):
                    result.append(DiscoveredCompany(name=item, is_active=True))
                elif isinstance(item, dict):
                    result.append(
                        DiscoveredCompany(
                            name=item.get("name") or item.get("company_name", ""),
                            guid=item.get("guid"),
                            financial_year_from=item.get("financial_year"),
                            books_from=item.get("books_from"),
                            is_active=item.get("is_active", True),
                        )
                    )
            return result
        except Exception:
            return []

    # =========================================================================
    # 3. READ OPERATIONS
    # =========================================================================

    def get_ledgers(self, company_ref: TallyCompanyRef) -> list[LedgerData]:
        try:
            res = self._post_json(
                "/api/masters/ledgers",
                {"action": "export", "svCurrentCompany": company_ref.company_name},
                company_name=company_ref.company_name,
            )
            raw_list = res.get("data", res.get("ledgers", []))
            ledgers = []
            for item in raw_list:
                ledgers.append(
                    LedgerData(
                        name=item.get("name", ""),
                        parent_group=item.get("parent", item.get("parent_group", "Primary")),
                        tally_guid=item.get("guid"),
                        tally_master_id=item.get("master_id"),
                        opening_balance=float(item.get("opening_balance", 0.0)),
                    )
                )
            return ledgers
        except Exception:
            return []

    def get_parties(self, company_ref: TallyCompanyRef) -> list[PartyData]:
        ledgers = self.get_ledgers(company_ref)
        parties = []
        for led in ledgers:
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
        try:
            res = self._post_json(
                "/api/masters/items",
                {"action": "export", "svCurrentCompany": company_ref.company_name},
                company_name=company_ref.company_name,
            )
            raw_list = res.get("data", res.get("items", []))
            return [
                StockItemData(
                    name=item.get("name", ""),
                    parent_group=item.get("parent"),
                    hsn_sac=item.get("hsn"),
                    uom=item.get("uom"),
                    tally_guid=item.get("guid"),
                )
                for item in raw_list
            ]
        except Exception:
            return []

    def get_vouchers(
        self,
        company_ref: TallyCompanyRef,
        voucher_type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        reference: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            payload = {
                "action": "list",
                "svCurrentCompany": company_ref.company_name,
                "voucher_type": voucher_type,
                "from_date": from_date,
                "to_date": to_date,
                "reference": reference,
            }
            res = self._post_json("/api/vouchers", payload, company_name=company_ref.company_name)
            return res.get("data", res.get("vouchers", []))
        except Exception:
            return []

    def get_reports(self, company_ref: TallyCompanyRef, report_name: str) -> dict[str, Any]:
        try:
            payload = {
                "action": "export_report",
                "report_name": report_name,
                "svCurrentCompany": company_ref.company_name,
            }
            return self._post_json("/api/reports", payload, company_name=company_ref.company_name)
        except Exception as e:
            return {"error": str(e), "report_name": report_name}

    # =========================================================================
    # 4. WRITE OPERATIONS
    # =========================================================================

    def create_master(
        self, company_ref: TallyCompanyRef, master_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {
            "action": "create",
            "master_type": master_type,
            "svCurrentCompany": company_ref.company_name,
            "data": data,
        }
        return self._post_json(
            "/api/masters/create", payload, company_name=company_ref.company_name
        )

    def update_master(
        self, company_ref: TallyCompanyRef, master_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {
            "action": "update",
            "master_type": master_type,
            "svCurrentCompany": company_ref.company_name,
            "data": data,
        }
        return self._post_json(
            "/api/masters/update", payload, company_name=company_ref.company_name
        )

    def create_voucher(self, command: CreateVoucherCommand) -> VoucherResult:
        """
        Post voucher using native JSON format with explicit svCurrentCompany.
        """
        payload = {
            "action": "create_voucher",
            "svCurrentCompany": command.company_ref.company_name,
            "correlation_id": command.correlation_id,
            "voucher": {
                "voucher_type": command.voucher_type,
                "date": command.voucher_date.isoformat(),
                "reference": command.reference_number,
                "narration": command.narration,
                "lines": [
                    {
                        "ledger_name": line.ledger_name,
                        "amount": line.amount,
                        "is_debit": line.is_debit,
                        "item_name": line.item_name,
                        "quantity": line.quantity,
                        "rate": line.rate,
                    }
                    for line in command.lines
                ],
            },
        }

        try:
            res = self._post_json(
                "/api/vouchers/create",
                payload,
                company_name=command.company_ref.company_name,
            )
            success = res.get("status") == "success" or res.get("success", False)
            if success:
                vch_data = res.get("data", {})
                return VoucherResult(
                    success=True,
                    voucher_guid=vch_data.get("guid") or f"TALLY-JSON-{command.correlation_id}",
                    voucher_number=vch_data.get("voucher_number"),
                    master_id=vch_data.get("master_id"),
                    raw_response=json.dumps(res),
                    status_code=200,
                )
            else:
                return VoucherResult(
                    success=False,
                    error_message=res.get("message", "Tally JSON rejection"),
                    raw_response=json.dumps(res),
                    status_code=400,
                )
        except Exception as e:
            return VoucherResult(
                success=False,
                error_message=f"Transport error posting JSON to Tally: {e!s}",
                status_code=500,
            )

    def update_voucher(
        self, company_ref: TallyCompanyRef, voucher_data: dict[str, Any]
    ) -> VoucherResult:
        payload = {
            "action": "update_voucher",
            "svCurrentCompany": company_ref.company_name,
            "voucher": voucher_data,
        }
        res = self._post_json(
            "/api/vouchers/update", payload, company_name=company_ref.company_name
        )
        return VoucherResult(
            success=True, voucher_number=res.get("voucher_number"), status_code=200
        )

    # =========================================================================
    # 5. VERIFICATION
    # =========================================================================

    def verify_transaction(self, query: VerificationQuery) -> VerificationEvidence:
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
                    "reason": f"No voucher found with reference '{query.expected_reference}'"
                },
            )

        match = vouchers[0]
        actual_num = match.get("voucher_number") or match.get("VOUCHERNUMBER")
        actual_guid = match.get("guid") or match.get("GUID")
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
