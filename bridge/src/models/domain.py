from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.models.capabilities import TallyCapabilities


class TallyCompanyRef(BaseModel):
    """
    Explicit company selection reference.
    Enforces the hierarchy: Organization -> WAAST360 Company -> Tally Instance -> Tally Company.
    Prevents fallback to Tally's active company (svCurrentCompany safety).
    """

    company_name: str = Field(description="Exact company name as registered in Tally")
    tally_guid: str | None = Field(default=None, description="Tally-native unique GUID if known")
    tally_instance_id: str | None = Field(default=None, description="WAAST360 TallyInstance UUID")
    waast_company_id: str | None = Field(default=None, description="WAAST360 Company UUID")


class TallyStatus(BaseModel):
    """Health & connection state of the local Tally runtime."""

    is_online: bool
    host: str
    port: int
    tally_version: str = "Unknown"
    response_time_ms: float = 0.0
    capabilities: TallyCapabilities = Field(default_factory=TallyCapabilities)
    error_message: str | None = None


class DiscoveredCompany(BaseModel):
    """Metadata for a company discovered inside the Tally Instance."""

    name: str
    guid: str | None = None
    financial_year_from: str | None = None
    books_from: str | None = None
    is_active: bool = True
    company_number: str | None = None


class LedgerData(BaseModel):
    name: str
    parent_group: str
    tally_guid: str | None = None
    tally_master_id: int | None = None
    opening_balance: float = 0.0
    is_active: bool = True


class PartyData(BaseModel):
    name: str
    party_type: str  # CREDITOR or DEBTOR
    parent_group: str
    gstin: str | None = None
    pan: str | None = None
    state: str | None = None
    tally_guid: str | None = None


class StockItemData(BaseModel):
    name: str
    parent_group: str | None = None
    hsn_sac: str | None = None
    uom: str | None = None
    tally_guid: str | None = None


class VoucherLineData(BaseModel):
    ledger_name: str
    amount: float
    is_debit: bool
    item_name: str | None = None
    quantity: float | None = None
    rate: float | None = None


class VoucherData(BaseModel):
    voucher_type: str
    voucher_number: str | None = None
    reference: str | None = None
    date: str | None = None
    guid: str | None = None
    amount: float | None = None


class CreateVoucherCommand(BaseModel):
    """
    Domain command for voucher creation.
    Encapsulates all necessary data independent of whether transport uses JSON or XML.
    """

    company_ref: TallyCompanyRef
    voucher_type: str  # Purchase, Sales, Payment, Receipt, Journal
    voucher_date: date
    reference_number: str | None = None
    narration: str | None = None
    lines: list[VoucherLineData]
    correlation_id: str = Field(description="Deterministic idempotency key for this posting")


class VoucherResult(BaseModel):
    success: bool
    voucher_guid: str | None = None
    voucher_number: str | None = None
    master_id: int | None = None
    error_message: str | None = None
    raw_response: str | None = None
    status_code: int = 200


class VerificationQuery(BaseModel):
    """Query parameters to verify if a voucher was persisted in Tally."""

    company_ref: TallyCompanyRef
    correlation_id: str
    expected_voucher_number: str | None = None
    expected_reference: str | None = None
    expected_amount: float | None = None
    voucher_type: str | None = None
    voucher_date: date | None = None


class VerificationEvidence(BaseModel):
    """Forensic evidence gathered from Tally read-back."""

    is_verified: bool
    status: str  # VERIFIED, MISMATCH, NOT_FOUND, ERROR
    actual_voucher_number: str | None = None
    actual_guid: str | None = None
    actual_amount: float | None = None
    mismatch_details: dict[str, Any] | None = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SyncResult(BaseModel):
    sync_type: str
    company_name: str
    records_count: int
    items: list[dict[str, Any]] = Field(default_factory=list)
    success: bool = True
    error_message: str | None = None
