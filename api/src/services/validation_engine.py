from typing import Any

from pydantic import BaseModel


class ValidationRuleResult(BaseModel):
    rule_code: str
    severity: str  # INFO, WARNING, ERROR, BLOCKER
    is_passed: bool
    message: str
    details: dict[str, Any] = {}


class ValidationEngine:
    """
    Deterministic rules and GST validation engine.
    Ensures accounting invariants are strictly enforced by deterministic algorithms,
    never by stochastic LLM guessing.
    """

    @staticmethod
    def validate_double_entry_balance(
        debit_lines: list[dict[str, Any]],
        credit_lines: list[dict[str, Any]],
    ) -> ValidationRuleResult:
        """Rule VAL-001: Total Debits must exactly equal Total Credits."""
        total_debit = sum(float(line.get("amount", 0.0)) for line in debit_lines)
        total_credit = sum(float(line.get("amount", 0.0)) for line in credit_lines)

        diff = abs(total_debit - total_credit)
        is_balanced = diff <= 0.01

        return ValidationRuleResult(
            rule_code="VAL-RULE-001",
            severity="BLOCKER" if not is_balanced else "INFO",
            is_passed=is_balanced,
            message="Double-entry balance verified: Debits equal Credits."
            if is_balanced
            else f"Double-entry imbalance: Debits ({total_debit:.2f}) != Credits ({total_credit:.2f}), diff: {diff:.2f}",
            details={"total_debit": total_debit, "total_credit": total_credit, "difference": diff},
        )

    @staticmethod
    def validate_gst_mathematics(
        taxable_amount: float,
        cgst_amount: float,
        sgst_amount: float,
        igst_amount: float,
        round_off: float,
        total_amount: float,
    ) -> ValidationRuleResult:
        """
        Rule VAL-002: Deterministic GST Invariant:
        Taxable + CGST + SGST + IGST + RoundOff == Total
        """
        calculated_total = taxable_amount + cgst_amount + sgst_amount + igst_amount + round_off
        diff = abs(calculated_total - total_amount)
        is_valid = diff <= 0.05

        return ValidationRuleResult(
            rule_code="VAL-RULE-002",
            severity="ERROR" if not is_valid else "INFO",
            is_passed=is_valid,
            message="GST mathematical integrity verified."
            if is_valid
            else f"GST math mismatch: Taxable+Taxes sum to {calculated_total:.2f}, but Total is {total_amount:.2f}",
            details={
                "taxable": taxable_amount,
                "cgst": cgst_amount,
                "sgst": sgst_amount,
                "igst": igst_amount,
                "round_off": round_off,
                "calculated_total": calculated_total,
                "expected_total": total_amount,
                "difference": diff,
            },
        )

    @staticmethod
    def validate_duplicate_invoice(
        invoice_number: str,
        vendor_name: str,
        existing_invoice_numbers: list[str],
    ) -> ValidationRuleResult:
        """Rule VAL-003: Prevent duplicate bills for the same vendor."""
        is_duplicate = invoice_number in existing_invoice_numbers
        return ValidationRuleResult(
            rule_code="VAL-RULE-003",
            severity="WARNING" if is_duplicate else "INFO",
            is_passed=not is_duplicate,
            message="No duplicate invoice reference detected."
            if not is_duplicate
            else f"Potential duplicate: Invoice '{invoice_number}' already exists for vendor '{vendor_name}'",
            details={"invoice_number": invoice_number, "is_duplicate": is_duplicate},
        )
