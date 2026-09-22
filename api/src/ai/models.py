from typing import Any

from pydantic import BaseModel, Field


class ExtractedLineItem(BaseModel):
    description: str
    hsn_code: str | None = None
    quantity: float = 1.0
    unit_price: float = 0.0
    taxable_amount: float = 0.0
    gst_rate: float = 18.0  # percentage, e.g. 18.0, 12.0, 5.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    total_amount: float = 0.0


class ExtractedInvoiceData(BaseModel):
    vendor_name: str = Field(description="Supplier / Seller Legal Name")
    vendor_gstin: str | None = Field(default=None, description="Supplier GSTIN (15 characters)")
    vendor_pan: str | None = Field(default=None, description="Supplier PAN (10 characters)")
    buyer_name: str | None = Field(default=None, description="Buyer / Consignee Legal Name")
    buyer_gstin: str | None = Field(default=None, description="Buyer GSTIN")
    invoice_number: str = Field(description="Unique Invoice / Bill Reference Number")
    invoice_date: str = Field(description="Invoice Date in YYYY-MM-DD format")
    currency: str = Field(default="INR", description="Invoice Currency")
    taxable_amount: float = Field(default=0.0, description="Total Taxable Value")
    cgst_amount: float = Field(default=0.0, description="Central GST Amount")
    sgst_amount: float = Field(default=0.0, description="State GST Amount")
    igst_amount: float = Field(default=0.0, description="Integrated GST Amount")
    round_off: float = Field(default=0.0, description="Round-off adjustment")
    total_amount: float = Field(description="Final Gross Invoice Total")
    line_items: list[ExtractedLineItem] = Field(default_factory=list)
    confidence: float = Field(default=0.95, description="Extraction confidence score (0.0 to 1.0)")
    raw_response: dict[str, Any] = Field(default_factory=dict)
