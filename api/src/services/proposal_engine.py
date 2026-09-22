from typing import Any

from src.ai.models import ExtractedInvoiceData
from src.services.validation_engine import ValidationEngine, ValidationRuleResult


class ProposedVoucherLine:
    def __init__(self, ledger_name: str, amount: float, is_debit: bool):
        self.ledger_name = ledger_name
        self.amount = round(amount, 2)
        self.is_debit = is_debit

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger_name": self.ledger_name,
            "amount": self.amount,
            "is_debit": self.is_debit,
        }


class ProposalEngine:
    """
    Constructs deterministic double-entry accounting proposals from extracted invoice data.
    """

    @classmethod
    def generate_proposal(
        cls,
        extracted: ExtractedInvoiceData,
        existing_invoices: list[str] | None = None,
    ) -> tuple[list[ProposedVoucherLine], list[ValidationRuleResult], bool]:
        """
        Convert extracted invoice into balanced double-entry voucher lines
        and run validation checks.
        Returns: (lines, validation_results, is_all_passed)
        """
        debit_lines = []
        credit_lines = []

        # 1. Purchase Account Debit
        if extracted.taxable_amount > 0:
            debit_lines.append(
                ProposedVoucherLine(
                    ledger_name="Purchase A/c",
                    amount=extracted.taxable_amount,
                    is_debit=True,
                )
            )

        # 2. GST Input Debits
        if extracted.cgst_amount > 0:
            debit_lines.append(
                ProposedVoucherLine(
                    ledger_name="Input CGST 9%",
                    amount=extracted.cgst_amount,
                    is_debit=True,
                )
            )
        if extracted.sgst_amount > 0:
            debit_lines.append(
                ProposedVoucherLine(
                    ledger_name="Input SGST 9%",
                    amount=extracted.sgst_amount,
                    is_debit=True,
                )
            )
        if extracted.igst_amount > 0:
            debit_lines.append(
                ProposedVoucherLine(
                    ledger_name="Input IGST 18%",
                    amount=extracted.igst_amount,
                    is_debit=True,
                )
            )

        # 3. Round-off adjustment
        if abs(extracted.round_off) > 0.001:
            debit_lines.append(
                ProposedVoucherLine(
                    ledger_name="Round Off",
                    amount=extracted.round_off,
                    is_debit=True,
                )
            )

        # 4. Supplier / Creditor Credit
        credit_lines.append(
            ProposedVoucherLine(
                ledger_name=extracted.vendor_name,
                amount=extracted.total_amount,
                is_debit=False,
            )
        )

        all_lines = debit_lines + credit_lines

        # Run Validation Engine
        validation_results = []

        # Check Rule 1: Double-Entry Balance
        balance_res = ValidationEngine.validate_double_entry_balance(
            [d_line.to_dict() for d_line in debit_lines],
            [c_line.to_dict() for c_line in credit_lines],
        )
        validation_results.append(balance_res)

        # Check Rule 2: GST Mathematics Invariant
        gst_res = ValidationEngine.validate_gst_mathematics(
            taxable_amount=extracted.taxable_amount,
            cgst_amount=extracted.cgst_amount,
            sgst_amount=extracted.sgst_amount,
            igst_amount=extracted.igst_amount,
            round_off=extracted.round_off,
            total_amount=extracted.total_amount,
        )
        validation_results.append(gst_res)

        # Check Rule 3: Duplicate Detection
        dup_res = ValidationEngine.validate_duplicate_invoice(
            invoice_number=extracted.invoice_number,
            vendor_name=extracted.vendor_name,
            existing_invoice_numbers=existing_invoices or [],
        )
        validation_results.append(dup_res)

        is_all_passed = all(
            r.is_passed or r.severity in ("INFO", "WARNING") for r in validation_results
        )

        return all_lines, validation_results, is_all_passed
