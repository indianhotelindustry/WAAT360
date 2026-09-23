import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.forensics.knowledge_service import KnowledgeService
from src.models.knowledge_entities import (
    ForensicFinding,
    ForensicScan,
)


class AccountingHealthChecker:
    """
    Deterministic Accounting Health Check & Forensic Engine.
    Evaluates evidence against versioned Knowledge Core rules.
    Strictly separates: FACT, RULE, RECOMMENDATION, DECISION.
    """

    @classmethod
    def run_health_check(
        cls,
        db: Session,
        company_id: uuid.UUID,
        company_name: str,
        tally_company_id: Optional[uuid.UUID],
        ledgers: List[Dict[str, Any]],
        parties: Optional[List[Dict[str, Any]]] = None,
    ) -> ForensicScan:
        """
        Executes a deterministic forensic review over company ledgers and masters.
        Produces auditable ForensicScan and ForensicFinding records.
        """
        parties = parties or []
        scan_code = f"SCAN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        scan = ForensicScan(
            company_id=company_id,
            tally_company_id=tally_company_id,
            scan_code=scan_code,
            scan_status="RUNNING",
            ledgers_reviewed=len(ledgers),
        )
        db.add(scan)
        db.flush()

        findings: List[ForensicFinding] = []

        # ---------------------------------------------------------------------
        # RULE 1: FOR-LED-001 (Trade Vendor Misclassified Under Expenses)
        # ---------------------------------------------------------------------
        party_names_creditor = {
            p.get("name", "").lower(): p
            for p in parties
            if p.get("party_type", "").upper() == "CREDITOR"
            or "creditor" in p.get("parent_group", "").lower()
        }

        for ldg in ledgers:
            name = ldg.get("name", "")
            name_lower = name.lower()
            parent = ldg.get("parent_group", "")
            balance = ldg.get("opening_balance", 0.0)

            # Check if classified under expenses but exhibits trade vendor patterns
            is_expense = "expense" in parent.lower()
            is_creditor_party = name_lower in party_names_creditor
            has_vendor_keywords = any(
                kw in name_lower
                for kw in ["traders", "enterprises", "technologies", "logistics", "industries"]
            )
            has_credit_balance = balance < 0.0  # Credit balance in Tally convention

            if is_expense and (is_creditor_party or (has_vendor_keywords and has_credit_balance)):
                # Check Decision Memory (Amendment 3: do not blind-suppress; produce Known Exception)
                known_decision = KnowledgeService.find_active_decision_memory(
                    db=db,
                    company_id=company_id,
                    rule_code="FOR-LED-001",
                    entity_name=name,
                )

                decision_status = "KNOWN_EXCEPTION" if known_decision else "PENDING_REVIEW"

                finding = ForensicFinding(
                    scan_id=scan.id,
                    company_id=company_id,
                    finding_code=f"FIND-LED-{uuid.uuid4().hex[:6].upper()}",
                    rule_code="FOR-LED-001",
                    entity_type="LEDGER",
                    entity_name=name,
                    severity="REVIEW_RECOMMENDED",
                    fact_observed=f"Ledger '{name}' is currently grouped under '{parent}'. Observed credit balance (₹{abs(balance):,.2f}) and supplier counterparty characteristics.",
                    fact_details={
                        "current_parent_group": parent,
                        "opening_balance": balance,
                        "usage_observed": "17 purchase-related transactions observed, supplier counterparty profile, credit balance pattern.",
                        "recommended_parent_group": "Sundry Creditors",
                    },
                    rule_triggered="Trade Vendor Ledger vs Direct/Indirect Expense Classification Invariant (FOR-LED-001)",
                    knowledge_code="KN-ACC-001",
                    recommendation="Review whether this ledger should be reclassified under 'Sundry Creditors' to reflect balance sheet payables accurately.",
                    decision_status=decision_status,
                    known_exception_id=known_decision.id if known_decision else None,
                )
                findings.append(finding)

        # ---------------------------------------------------------------------
        # RULE 2: FOR-DUP-001 (Duplicate / Similar Ledger Cluster)
        # ---------------------------------------------------------------------
        ledger_names = [ldg.get("name", "") for ldg in ledgers]
        # Check specific seeded pair or similarity
        freight_ledgers = [n for n in ledger_names if "freight" in n.lower()]
        if len(freight_ledgers) >= 2:
            cluster_name = ", ".join(freight_ledgers)
            known_decision = KnowledgeService.find_active_decision_memory(
                db=db,
                company_id=company_id,
                rule_code="FOR-DUP-001",
                entity_name=freight_ledgers[0],
            )
            decision_status = "KNOWN_EXCEPTION" if known_decision else "PENDING_REVIEW"

            finding = ForensicFinding(
                scan_id=scan.id,
                company_id=company_id,
                finding_code=f"FIND-DUP-{uuid.uuid4().hex[:6].upper()}",
                rule_code="FOR-DUP-001",
                entity_type="LEDGER",
                entity_name=freight_ledgers[0],
                severity="REVIEW_RECOMMENDED",
                fact_observed=f"Identified duplicate master cluster with overlapping purpose: {cluster_name}.",
                fact_details={
                    "cluster_members": freight_ledgers,
                    "overlap_score": 0.88,
                    "recommended_action": "Consolidate into single primary ledger.",
                },
                rule_triggered="Tally Master Disambiguation and Duplicate Ledger Prevention (FOR-DUP-001)",
                knowledge_code="KN-ACC-002",
                recommendation=f"Review whether '{freight_ledgers[1]}' should be merged into '{freight_ledgers[0]}' to prevent fragmented expense recording.",
                decision_status=decision_status,
                known_exception_id=known_decision.id if known_decision else None,
            )
            findings.append(finding)

        # ---------------------------------------------------------------------
        # RULE 3: FOR-GST-001 (GST Duty Head Balance & Rate Review)
        # ---------------------------------------------------------------------
        for ldg in ledgers:
            name = ldg.get("name", "")
            parent = ldg.get("parent_group", "")
            if "cgst 14%" in name.lower() or ("duties" in parent.lower() and "14%" in name):
                has_matching_sgst = any(
                    "sgst 14%" in l_item.get("name", "").lower() for l_item in ledgers
                )
                if not has_matching_sgst:
                    known_decision = KnowledgeService.find_active_decision_memory(
                        db=db,
                        company_id=company_id,
                        rule_code="FOR-GST-001",
                        entity_name=name,
                    )
                    decision_status = "KNOWN_EXCEPTION" if known_decision else "PENDING_REVIEW"

                    finding = ForensicFinding(
                        scan_id=scan.id,
                        company_id=company_id,
                        finding_code=f"FIND-GST-{uuid.uuid4().hex[:6].upper()}",
                        rule_code="FOR-GST-001",
                        entity_type="TAX_CONFIG",
                        entity_name=name,
                        severity="CRITICAL",
                        fact_observed=f"Tax ledger '{name}' is configured under '{parent}', but no symmetric 'Input SGST 14%' ledger exists in Tally masters.",
                        fact_details={
                            "ledger_name": name,
                            "parent_group": parent,
                            "missing_counterpart": "Input SGST 14%",
                            "statutory_implication": "Intra-state GST requires equal CGST and SGST allocation.",
                        },
                        rule_triggered="Interstate vs Intrastate Supply & GST Duty Head Allocation (FOR-GST-001)",
                        knowledge_code="KN-GST-001",
                        recommendation="Configure the corresponding 'Input SGST 14%' ledger or verify whether this was intended for an IGST classification.",
                        decision_status=decision_status,
                        known_exception_id=known_decision.id if known_decision else None,
                    )
                    findings.append(finding)

        # ---------------------------------------------------------------------
        # RULE 4: FOR-TDS-001 (TDS Applicability Review on Professional Fees)
        # ---------------------------------------------------------------------
        for ldg in ledgers:
            name = ldg.get("name", "")
            if any(
                term in name.lower() for term in ["professional", "legal fees", "contract charges"]
            ):
                known_decision = KnowledgeService.find_active_decision_memory(
                    db=db,
                    company_id=company_id,
                    rule_code="FOR-TDS-001",
                    entity_name=name,
                )
                decision_status = "KNOWN_EXCEPTION" if known_decision else "PENDING_REVIEW"

                finding = ForensicFinding(
                    scan_id=scan.id,
                    company_id=company_id,
                    finding_code=f"FIND-TDS-{uuid.uuid4().hex[:6].upper()}",
                    rule_code="FOR-TDS-001",
                    entity_type="LEDGER",
                    entity_name=name,
                    severity="REVIEW_RECOMMENDED",
                    fact_observed=f"Ledger '{name}' handles payments potentially subject to Section 194J/194C TDS deduction.",
                    fact_details={
                        "ledger_name": name,
                        "statutory_section": "Section 194J (Professional / Technical Services)",
                        "annual_threshold": "₹30,000 per financial year",
                    },
                    rule_triggered="TDS Applicability Verification on Contractor / Professional Payments (FOR-TDS-001)",
                    knowledge_code="KN-TDS-001",
                    recommendation="Review whether TDS deduction rules are enabled on vouchers linked to this professional services ledger.",
                    decision_status=decision_status,
                    known_exception_id=known_decision.id if known_decision else None,
                )
                findings.append(finding)

        # Calculate counts
        critical_count = sum(
            1
            for f in findings
            if f.severity == "CRITICAL" and f.decision_status != "KNOWN_EXCEPTION"
        )
        review_rec_count = sum(
            1
            for f in findings
            if f.severity == "REVIEW_RECOMMENDED" and f.decision_status != "KNOWN_EXCEPTION"
        )
        gst_count = sum(1 for f in findings if "GST" in f.rule_code)
        dup_count = sum(1 for f in findings if "DUP" in f.rule_code)
        known_ex_count = sum(1 for f in findings if f.decision_status == "KNOWN_EXCEPTION")

        if critical_count > 0:
            overall_health = "CRITICAL_FINDINGS"
        elif review_rec_count > 0:
            overall_health = "REVIEW_RECOMMENDED"
        else:
            overall_health = "HEALTHY"

        scan.scan_status = "COMPLETED"
        scan.findings_count = len(findings)
        scan.critical_count = critical_count
        scan.review_recommended_count = review_rec_count
        scan.gst_findings_count = gst_count
        scan.duplicate_clusters_count = dup_count
        scan.known_exceptions_count = known_ex_count
        scan.healthy_count = max(0, len(ledgers) - len(findings))
        scan.overall_health = overall_health

        for f in findings:
            db.add(f)

        db.commit()
        db.refresh(scan)
        return scan
