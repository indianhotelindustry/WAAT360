import uuid
from datetime import datetime, timezone
from typing import Any

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


class TallySimulatedAdapter(TallyAdapter):
    """
    High-fidelity simulated TallyAdapter for local development and testing.
    Implements the exact identical TallyAdapter contract as TallyJsonAdapter
    and TallyXmlAdapter, maintaining realistic in-memory Indian accounting state:
    companies, ledgers, GST duties, parties, sequential vouchers, and read-back verification.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9000, timeout_seconds: float = 10.0):
        super().__init__(host=host, port=port, timeout_seconds=timeout_seconds)
        self._is_online = True
        self._voucher_counter = 1

        # Realistic Companies
        self._companies = [
            DiscoveredCompany(
                name="Tata Motors Technologies Ltd",
                guid="TALLY-SIM-001",
                financial_year_from="2024-2025",
                books_from="2024-04-01",
                is_active=True,
            ),
            DiscoveredCompany(
                name="Acme Industrial Technologies Pvt Ltd",
                guid="TALLY-SIM-002",
                financial_year_from="2024-2025",
                books_from="2024-04-01",
                is_active=True,
            ),
            DiscoveredCompany(
                name="Shreeji Steel Enterprises",
                guid="TALLY-SIM-003",
                financial_year_from="2024-2025",
                books_from="2024-04-01",
                is_active=True,
            ),
        ]

        # Realistic Indian GST Ledgers
        self._ledgers = [
            LedgerData(name="Purchase A/c", parent_group="Purchase Accounts", opening_balance=0.0),
            LedgerData(name="Sales A/c", parent_group="Sales Accounts", opening_balance=0.0),
            LedgerData(name="Input CGST 9%", parent_group="Duties & Taxes", opening_balance=0.0),
            LedgerData(name="Input SGST 9%", parent_group="Duties & Taxes", opening_balance=0.0),
            LedgerData(name="Input IGST 18%", parent_group="Duties & Taxes", opening_balance=0.0),
            LedgerData(name="Output CGST 9%", parent_group="Duties & Taxes", opening_balance=0.0),
            LedgerData(name="Output SGST 9%", parent_group="Duties & Taxes", opening_balance=0.0),
            LedgerData(name="Round Off", parent_group="Indirect Expenses", opening_balance=0.0),
            LedgerData(
                name="HDFC Bank A/c", parent_group="Bank Accounts", opening_balance=150000.0
            ),
            LedgerData(name="Cash", parent_group="Cash-in-Hand", opening_balance=25000.0),
            LedgerData(
                name="Shreeji Steel Traders",
                parent_group="Sundry Creditors",
                opening_balance=-45000.0,
            ),
            LedgerData(
                name="Apex Raw Materials Ltd",
                parent_group="Sundry Creditors",
                opening_balance=-82000.0,
            ),
            LedgerData(
                name="Supreme Logistics & Transport",
                parent_group="Sundry Creditors",
                opening_balance=0.0,
            ),
            LedgerData(
                name="National Engineering Works",
                parent_group="Sundry Debtors",
                opening_balance=95000.0,
            ),
        ]

        # Parties (Sundry Creditors / Debtors)
        self._parties = [
            PartyData(
                name="Shreeji Steel Traders",
                party_type="CREDITOR",
                parent_group="Sundry Creditors",
                gstin="24AAACS1234F1Z8",
                state="Gujarat",
                opening_balance=-45000.0,
            ),
            PartyData(
                name="Apex Raw Materials Ltd",
                party_type="CREDITOR",
                parent_group="Sundry Creditors",
                gstin="27AAPCA5678B1ZG",
                state="Maharashtra",
                opening_balance=-82000.0,
            ),
            PartyData(
                name="Supreme Logistics & Transport",
                party_type="CREDITOR",
                parent_group="Sundry Creditors",
                gstin="24AALST9012C1ZH",
                state="Gujarat",
                opening_balance=0.0,
            ),
            PartyData(
                name="National Engineering Works",
                party_type="DEBTOR",
                parent_group="Sundry Debtors",
                gstin="24AABCN3456D1ZK",
                state="Gujarat",
                opening_balance=95000.0,
            ),
        ]

        # Stock Items
        self._stock_items = [
            StockItemData(
                name="Steel Bars 12mm", hsn_code="72142090", uom="KGS", standard_rate=65.0
            ),
            StockItemData(
                name="Industrial Fasteners M8", hsn_code="73181500", uom="NOS", standard_rate=12.5
            ),
            StockItemData(
                name="Mild Steel Plates 5mm", hsn_code="72085110", uom="KGS", standard_rate=78.0
            ),
        ]

        # In-memory Voucher Store: company_name -> list of vouchers
        self._vouchers: dict[str, list[dict[str, Any]]] = {}

    # =========================================================================
    # 1. CONNECTION & CAPABILITIES
    # =========================================================================

    def test_connection(self) -> bool:
        return self._is_online

    def get_tally_status(self) -> TallyStatus:
        return TallyStatus(
            is_online=self._is_online,
            host=self.host,
            port=self.port,
            tally_version="TallyPrime 7.0 (Simulated Dev/Demo)",
            response_time_ms=8.5,
            capabilities=self.discover_capabilities(),
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
            tally_version="TallyPrime 7.0 (Simulated)",
        )

    # =========================================================================
    # 2. DISCOVERY
    # =========================================================================

    def get_companies(self) -> list[DiscoveredCompany]:
        return list(self._companies)

    # =========================================================================
    # 3. READ OPERATIONS
    # =========================================================================

    def get_ledgers(self, company_ref: TallyCompanyRef) -> list[LedgerData]:
        return list(self._ledgers)

    def get_parties(self, company_ref: TallyCompanyRef) -> list[PartyData]:
        return list(self._parties)

    def get_stock_items(self, company_ref: TallyCompanyRef) -> list[StockItemData]:
        return list(self._stock_items)

    def get_vouchers(
        self,
        company_ref: TallyCompanyRef,
        voucher_type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        reference: str | None = None,
    ) -> list[dict[str, Any]]:
        c_vouchers = self._vouchers.get(company_ref.company_name, [])
        results = []
        for v in c_vouchers:
            if voucher_type and v.get("voucher_type") != voucher_type:
                continue
            if reference and v.get("reference_number") != reference:
                continue
            results.append(v)
        return results

    def get_reports(self, company_ref: TallyCompanyRef, report_name: str) -> dict[str, Any]:
        return {
            "report_name": report_name,
            "company_name": company_ref.company_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "status": "success",
                "rows": len(self._vouchers.get(company_ref.company_name, [])),
            },
        }

    # =========================================================================
    # 4. WRITE OPERATIONS
    # =========================================================================

    def create_master(
        self, company_ref: TallyCompanyRef, master_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        name = data.get("name", f"Master-{uuid.uuid4().hex[:6]}")
        if master_type.upper() == "LEDGER":
            parent = data.get("parent_group", "Sundry Creditors")
            self._ledgers.append(LedgerData(name=name, parent_group=parent))
        return {"status": "created", "master_type": master_type, "name": name}

    def update_master(
        self, company_ref: TallyCompanyRef, master_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return {"status": "updated", "master_type": master_type, "name": data.get("name")}

    def create_voucher(self, command: CreateVoucherCommand) -> VoucherResult:
        comp_name = command.company_ref.company_name
        if comp_name not in self._vouchers:
            self._vouchers[comp_name] = []

        # Check for duplicate posting by correlation_id or reference_number
        for existing in self._vouchers[comp_name]:
            if command.correlation_id and existing.get("correlation_id") == command.correlation_id:
                return VoucherResult(
                    success=True,
                    voucher_number=existing["voucher_number"],
                    voucher_guid=existing["guid"],
                    status_code=200,
                    error_message=None,
                    raw_response="Reconciled existing simulated voucher",
                )
            if (
                command.reference_number
                and existing.get("reference_number") == command.reference_number
            ):
                return VoucherResult(
                    success=True,
                    voucher_number=existing["voucher_number"],
                    voucher_guid=existing["guid"],
                    status_code=200,
                    error_message=None,
                    raw_response="Reconciled existing simulated voucher by reference",
                )

        # Generate realistic Tally sequential voucher number & GUID
        vch_number = f"PUR/2026/{self._voucher_counter:04d}"
        vch_guid = f"TALLY-GUID-VCH-{uuid.uuid4().hex[:12].upper()}"
        self._voucher_counter += 1

        total_amount = sum(line.amount for line in command.lines if line.is_debit)

        stored_voucher = {
            "voucher_number": vch_number,
            "guid": vch_guid,
            "voucher_type": command.voucher_type,
            "voucher_date": command.voucher_date.isoformat(),
            "reference_number": command.reference_number,
            "narration": command.narration,
            "total_amount": total_amount,
            "correlation_id": command.correlation_id,
            "lines": [line.model_dump() for line in command.lines],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._vouchers[comp_name].append(stored_voucher)

        return VoucherResult(
            success=True,
            voucher_number=vch_number,
            voucher_guid=vch_guid,
            status_code=200,
            raw_response="Simulated TallyPrime response: CREATED=1, ALTERED=0, ERRORS=0",
        )

    def update_voucher(
        self, company_ref: TallyCompanyRef, voucher_data: dict[str, Any]
    ) -> VoucherResult:
        return VoucherResult(
            success=True,
            voucher_number=voucher_data.get("voucher_number", "UPDATED"),
            status_code=200,
        )

    # =========================================================================
    # 5. VERIFICATION
    # =========================================================================

    def verify_transaction(self, query: VerificationQuery) -> VerificationEvidence:
        """
        Forensically read back from in-memory Tally store to verify if voucher exists.
        Matches by reference number, correlation_id, or expected voucher number and validates amounts.
        """
        c_vouchers = self._vouchers.get(query.company_ref.company_name, [])

        matched = None
        for v in c_vouchers:
            if query.correlation_id and v.get("correlation_id") == query.correlation_id:
                matched = v
                break
            if query.expected_reference and v.get("reference_number") == query.expected_reference:
                matched = v
                break

        if not matched:
            return VerificationEvidence(
                is_verified=False,
                status="NOT_FOUND",
                mismatch_details={"error": "Voucher not found in Tally records"},
            )

        # Check amount match
        actual_amount = float(matched.get("total_amount", 0.0))
        if query.expected_amount is not None:
            diff = abs(actual_amount - query.expected_amount)
            if diff > 0.01:
                return VerificationEvidence(
                    is_verified=False,
                    status="AMOUNT_MISMATCH",
                    actual_voucher_number=matched["voucher_number"],
                    actual_guid=matched["guid"],
                    actual_amount=actual_amount,
                    mismatch_details={
                        "expected_amount": query.expected_amount,
                        "actual_amount": actual_amount,
                        "difference": diff,
                    },
                )

        return VerificationEvidence(
            is_verified=True,
            status="VERIFIED",
            actual_voucher_number=matched["voucher_number"],
            actual_guid=matched["guid"],
            actual_amount=actual_amount,
            mismatch_details=None,
            raw_payload=matched,
        )

    # =========================================================================
    # 6. SYNCHRONIZATION
    # =========================================================================

    def sync_from_tally(self, company_ref: TallyCompanyRef, sync_type: str) -> SyncResult:
        if sync_type.upper() == "COMPANIES":
            records = [c.model_dump() for c in self._companies]
        elif sync_type.upper() == "LEDGERS":
            records = [ledger.model_dump() for ledger in self._ledgers]

        elif sync_type.upper() == "PARTIES":
            records = [p.model_dump() for p in self._parties]
        else:
            records = []

        return SyncResult(
            sync_type=sync_type,
            records_count=len(records),
            records=records,
            timestamp=datetime.now(timezone.utc),
        )

    def sync_to_tally(
        self,
        company_ref: TallyCompanyRef,
        sync_type: str,
        records: list[dict[str, Any]],
    ) -> SyncResult:
        return SyncResult(
            sync_type=sync_type,
            records_count=len(records),
            records=[],
            timestamp=datetime.now(timezone.utc),
        )
