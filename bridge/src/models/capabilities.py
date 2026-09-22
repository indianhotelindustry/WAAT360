from pydantic import BaseModel, Field


class TallyCapabilities(BaseModel):
    """
    Capability discovery model.
    Different Tally versions (TallyPrime 7.0 vs older) have varying feature support.
    """

    supports_json: bool = Field(
        default=False, description="Whether Tally natively supports JSON endpoints"
    )
    supports_xml: bool = Field(
        default=True,
        description="Whether Tally supports standard XML envelope communication",
    )
    supports_master_read: bool = Field(
        default=True, description="Ability to read chart of accounts/ledgers/parties"
    )
    supports_voucher_read: bool = Field(
        default=True, description="Ability to query vouchers by ID/date/number"
    )
    supports_voucher_write: bool = Field(
        default=True, description="Ability to post new accounting vouchers"
    )
    supports_report_read: bool = Field(
        default=False, description="Ability to export financial reports"
    )
    supports_company_discovery: bool = Field(
        default=True, description="Ability to list active/loaded companies"
    )
    tally_version: str = Field(
        default="Unknown", description="Detected Tally version/release string"
    )
