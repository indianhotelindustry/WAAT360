from abc import ABC, abstractmethod
from typing import Any

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


class TallyAdapter(ABC):
    """
    Abstract capability-based TallyAdapter interface.
    Decouples WAAST360 domain operations from whether Tally communication
    uses JSON (TallyPrime 7.0+) or XML envelopes (standard compatibility).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9000, timeout_seconds: float = 10.0):
        self.host = host
        self.port = port
        self.timeout_seconds = timeout_seconds
        self.endpoint_url = f"http://{host}:{port}"

    # =========================================================================
    # 1. CONNECTION & CAPABILITIES
    # =========================================================================

    @abstractmethod
    def test_connection(self) -> bool:
        """Ping Tally and return True if reachable."""

    @abstractmethod
    def get_tally_status(self) -> TallyStatus:
        """Return connectivity status, version, and detected capabilities."""

    @abstractmethod
    def discover_capabilities(self) -> TallyCapabilities:
        """Inspect Tally capabilities and return feature flags."""

    # =========================================================================
    # 2. DISCOVERY
    # =========================================================================

    @abstractmethod
    def get_companies(self) -> list[DiscoveredCompany]:
        """Query and return all active/loaded companies in this Tally Instance."""

    # =========================================================================
    # 3. READ OPERATIONS
    # =========================================================================

    @abstractmethod
    def get_ledgers(self, company_ref: TallyCompanyRef) -> list[LedgerData]:
        """Fetch chart of accounts / ledgers for the specified Tally company."""

    @abstractmethod
    def get_parties(self, company_ref: TallyCompanyRef) -> list[PartyData]:
        """Fetch Sundry Creditors & Debtors for the specified Tally company."""

    @abstractmethod
    def get_stock_items(self, company_ref: TallyCompanyRef) -> list[StockItemData]:
        """Fetch stock/service items for the specified Tally company."""

    @abstractmethod
    def get_vouchers(
        self,
        company_ref: TallyCompanyRef,
        voucher_type: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        reference: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query vouchers matching specified criteria."""

    @abstractmethod
    def get_reports(self, company_ref: TallyCompanyRef, report_name: str) -> dict[str, Any]:
        """Retrieve named accounting report from Tally."""

    # =========================================================================
    # 4. WRITE OPERATIONS
    # =========================================================================

    @abstractmethod
    def create_master(
        self, company_ref: TallyCompanyRef, master_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a master record (Ledger, Group, StockItem, etc.) in Tally."""

    @abstractmethod
    def update_master(
        self, company_ref: TallyCompanyRef, master_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing master record in Tally."""

    @abstractmethod
    def create_voucher(self, command: CreateVoucherCommand) -> VoucherResult:
        """
        Post an approved accounting voucher to Tally.
        Must explicitly specify svCurrentCompany to prevent fallback to active company.
        """

    @abstractmethod
    def update_voucher(
        self, company_ref: TallyCompanyRef, voucher_data: dict[str, Any]
    ) -> VoucherResult:
        """Alter an existing voucher in Tally."""

    # =========================================================================
    # 5. VERIFICATION
    # =========================================================================

    @abstractmethod
    def verify_transaction(self, query: VerificationQuery) -> VerificationEvidence:
        """
        Forensically read back from Tally to verify if a voucher was recorded.
        Matches by reference number, amount, date, and party identity.
        """

    # =========================================================================
    # 6. SYNCHRONIZATION
    # =========================================================================

    @abstractmethod
    def sync_from_tally(self, company_ref: TallyCompanyRef, sync_type: str) -> SyncResult:
        """Pull a batch of masters or data from Tally (LEDGERS, PARTIES, ITEMS)."""

    @abstractmethod
    def sync_to_tally(
        self,
        company_ref: TallyCompanyRef,
        sync_type: str,
        records: list[dict[str, Any]],
    ) -> SyncResult:
        """Push batch updates to Tally."""
