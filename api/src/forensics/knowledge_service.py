import uuid
from datetime import date
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.knowledge_entities import (
    CompanyKnowledgeProfile,
    DecisionMemory,
    KnowledgeItem,
    KnowledgeSource,
)


class KnowledgeService:
    """
    Controlled institutional knowledge service with provenance, versioning,
    effective date boundaries, and multi-tenant isolation.
    """

    @staticmethod
    def seed_initial_knowledge(db: Session) -> None:
        """
        Seeds official and verified knowledge items with complete source attribution.
        Idempotent: updates existing or creates if absent.
        """
        sources_def = [
            {
                "source_code": "SRC-CBIC-GST-01",
                "authority_name": "Central Board of Indirect Taxes and Customs (CBIC), Ministry of Finance, Govt of India",
                "source_type": "OFFICIAL_AUTHORITATIVE",
                "reference_url": "https://cbic-gst.gov.in",
                "citation": "Central Goods and Services Tax Act, 2017 (Act No. 12 of 2017), Section 7 & Section 9",
                "jurisdiction": "IN",
                "is_verified": True,
                "reviewed_by": "Lead Tax Counsel",
            },
            {
                "source_code": "SRC-CBDT-TDS-01",
                "authority_name": "Central Board of Direct Taxes (CBDT), Department of Revenue, Govt of India",
                "source_type": "OFFICIAL_AUTHORITATIVE",
                "reference_url": "https://incometaxindia.gov.in",
                "citation": "Income-tax Act, 1961, Section 194C & Section 194J",
                "jurisdiction": "IN",
                "is_verified": True,
                "reviewed_by": "Lead Tax Counsel",
            },
            {
                "source_code": "SRC-ICAI-AS-01",
                "authority_name": "Institute of Chartered Accountants of India (ICAI)",
                "source_type": "OFFICIAL_AUTHORITATIVE",
                "reference_url": "https://www.icai.org",
                "citation": "Accounting Standard (AS) 1: Disclosure of Accounting Policies; Framework for Financial Statements",
                "jurisdiction": "IN",
                "is_verified": True,
                "reviewed_by": "Senior Forensic Auditor",
            },
            {
                "source_code": "SRC-TALLY-DOC-01",
                "authority_name": "Tally Solutions Pvt. Ltd.",
                "source_type": "OFFICIAL_AUTHORITATIVE",
                "reference_url": "https://help.tallysolutions.com",
                "citation": "TallyPrime Master Hierarchy and Ledger Architecture Guide v3.0+",
                "jurisdiction": "IN",
                "is_verified": True,
                "reviewed_by": "Tally Integration Specialist",
            },
            {
                "source_code": "SRC-WAAST-RULES-01",
                "authority_name": "WAAST360 Forensic Rules & Invariants Engine",
                "source_type": "VERIFIED_WAAST_KNOWLEDGE",
                "reference_url": "https://waast360.internal/governance",
                "citation": "WAAST360 Deterministic Forensic Verification Ruleset v1.0",
                "jurisdiction": "IN",
                "is_verified": True,
                "reviewed_by": "Principal Forensic Engineer",
            },
        ]

        source_map = {}
        for s_data in sources_def:
            stmt = select(KnowledgeSource).where(
                KnowledgeSource.source_code == s_data["source_code"]
            )
            src = db.scalars(stmt).first()
            if not src:
                src = KnowledgeSource(**s_data)
                db.add(src)
                db.flush()
            source_map[src.source_code] = src.id

        items_def = [
            {
                "knowledge_code": "KN-GST-001",
                "domain": "GST_TAX",
                "title": "Interstate vs Intrastate Supply & Tax Head Allocation",
                "content": "Where supplier location and place of supply are in distinct states, Integrated Goods and Services Tax (IGST) applies. For intra-state supply, Central GST (CGST) and State GST (SGST) apply equally at half the total rate. Separate CGST and SGST ledgers must maintain balanced tax allocation.",
                "source_id": source_map["SRC-CBIC-GST-01"],
                "jurisdiction": "IN",
                "effective_from": date(2017, 7, 1),
                "effective_until": None,
                "rule_version": 1,
                "tally_version_pattern": "TallyPrime 1.0+",
                "status": "ACTIVE",
                "confidence": 1.00,
            },
            {
                "knowledge_code": "KN-GST-002",
                "domain": "GST_TAX",
                "title": "GSTIN 15-Digit Alphanumeric Structure Invariant",
                "content": "A valid Indian GSTIN consists of 15 characters: 2 digits (State Code), 10 characters (PAN), 1 entity code, 1 'Z' default character, and 1 check code. Party records claiming GST registration must possess a structurally valid GSTIN.",
                "source_id": source_map["SRC-CBIC-GST-01"],
                "jurisdiction": "IN",
                "effective_from": date(2017, 7, 1),
                "effective_until": None,
                "rule_version": 1,
                "tally_version_pattern": "TallyPrime 1.0+",
                "status": "ACTIVE",
                "confidence": 1.00,
            },
            {
                "knowledge_code": "KN-ACC-001",
                "domain": "ACCOUNTING",
                "title": "Trade Vendor Ledger vs Direct/Indirect Expense Classification",
                "content": "Ledgers representing external trade counterparties (suppliers of goods and services) must be classified under 'Sundry Creditors' to reflect financial liability. Grouping trade vendor accounts directly under 'Indirect Expenses' misrepresents operating expenses and obscures trade payable aging.",
                "source_id": source_map["SRC-ICAI-AS-01"],
                "jurisdiction": "IN",
                "effective_from": date(2000, 1, 1),
                "effective_until": None,
                "rule_version": 1,
                "tally_version_pattern": "TallyPrime 1.0+",
                "status": "ACTIVE",
                "confidence": 1.00,
            },
            {
                "knowledge_code": "KN-ACC-002",
                "domain": "ACCOUNTING",
                "title": "Tally Master Disambiguation and Duplicate Ledger Prevention",
                "content": "Duplicate or near-duplicate ledgers for identical accounting entities (e.g. 'Freight Charges' and 'Freight & Cartage') lead to fragmented ledgers and reporting discrepancies. Ledger names must be consolidated.",
                "source_id": source_map["SRC-TALLY-DOC-01"],
                "jurisdiction": "IN",
                "effective_from": date(2020, 1, 1),
                "effective_until": None,
                "rule_version": 1,
                "tally_version_pattern": "TallyPrime 2.0+",
                "status": "ACTIVE",
                "confidence": 1.00,
            },
            {
                "knowledge_code": "KN-TDS-001",
                "domain": "TDS_TCS",
                "title": "TDS Applicability Verification on Contractor / Professional Payments",
                "content": "Payments to contractors (Section 194C) and fees for professional/technical services (Section 194J) are subject to Tax Deducted at Source when exceeding statutory annual thresholds. Ledgers designated for professional fees, legal expenses, or contract work require review for appropriate TDS ledger mapping.",
                "source_id": source_map["SRC-CBDT-TDS-01"],
                "jurisdiction": "IN",
                "effective_from": date(2020, 4, 1),
                "effective_until": None,
                "rule_version": 1,
                "tally_version_pattern": "TallyPrime 1.0+",
                "status": "ACTIVE",
                "confidence": 1.00,
            },
            {
                "knowledge_code": "KN-FOR-001",
                "domain": "FORENSIC_RULES",
                "title": "Accounting Health Check Deterministic Evidence Rules",
                "content": "Forensic findings are triggered solely by factual structural inconsistencies verified against authoritative rules. Findings are classified as Healthy, Review Recommended, or Critical Finding, with full provenance attribution.",
                "source_id": source_map["SRC-WAAST-RULES-01"],
                "jurisdiction": "IN",
                "effective_from": date(2026, 1, 1),
                "effective_until": None,
                "rule_version": 1,
                "tally_version_pattern": "TallyPrime 1.0+",
                "status": "ACTIVE",
                "confidence": 1.00,
            },
        ]

        for item_data in items_def:
            stmt = select(KnowledgeItem).where(
                KnowledgeItem.knowledge_code == item_data["knowledge_code"]
            )
            existing = db.scalars(stmt).first()
            if not existing:
                item = KnowledgeItem(**item_data)
                db.add(item)
            else:
                for k, v in item_data.items():
                    setattr(existing, k, v)

        db.commit()

    @staticmethod
    def get_knowledge_items(
        db: Session,
        domain: Optional[str] = None,
        effective_on: Optional[date] = None,
        status: str = "ACTIVE",
    ) -> List[KnowledgeItem]:
        """
        Retrieves knowledge items with optional domain filtering and temporal validity checks.
        """
        stmt = select(KnowledgeItem).where(KnowledgeItem.status == status)
        if domain:
            stmt = stmt.where(KnowledgeItem.domain == domain)
        if effective_on:
            stmt = stmt.where(
                (KnowledgeItem.effective_from <= effective_on)
                & (
                    (KnowledgeItem.effective_until.is_(None))
                    | (KnowledgeItem.effective_until >= effective_on)
                )
            )
        stmt = stmt.order_by(KnowledgeItem.knowledge_code.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_knowledge_by_code(db: Session, knowledge_code: str) -> Optional[KnowledgeItem]:
        stmt = select(KnowledgeItem).where(KnowledgeItem.knowledge_code == knowledge_code)
        return db.scalars(stmt).first()

    # =========================================================================
    # MULTI-TENANT COMPANY KNOWLEDGE & DECISION MEMORY
    # =========================================================================

    @staticmethod
    def get_or_create_company_profile(
        db: Session, company_id: uuid.UUID
    ) -> CompanyKnowledgeProfile:
        """
        Retrieves or initializes the normalized CompanyKnowledgeProfile context anchor.
        """
        stmt = select(CompanyKnowledgeProfile).where(
            CompanyKnowledgeProfile.company_id == company_id
        )
        prof = db.scalars(stmt).first()
        if not prof:
            prof = CompanyKnowledgeProfile(
                company_id=company_id,
                accounting_policy_references={},
                notes="Initialized WAAST360 Company Knowledge Context Profile",
            )
            db.add(prof)
            db.commit()
            db.refresh(prof)
        return prof

    @staticmethod
    def record_decision_memory(
        db: Session,
        company_id: uuid.UUID,
        finding_code: str,
        rule_code: str,
        entity_type: str,
        entity_name: str,
        current_state: dict,
        recommended_state: dict,
        decision_reason: str,
        actor_id: str,
        actor_role: str = "CONTROLLER",
        human_decision: str = "KNOWN_EXCEPTION",
    ) -> DecisionMemory:
        """
        Records an auditable human decision in multi-tenant DecisionMemory.
        Ensures Company A decision memory NEVER leaks into Company B.
        """
        decision = DecisionMemory(
            company_id=company_id,
            finding_code=finding_code,
            rule_code=rule_code,
            entity_type=entity_type,
            entity_name=entity_name,
            current_state=current_state,
            recommended_state=recommended_state,
            human_decision=human_decision,
            decision_reason=decision_reason,
            actor_id=actor_id,
            actor_role=actor_role,
            is_active=True,
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)
        return decision

    @staticmethod
    def find_active_decision_memory(
        db: Session,
        company_id: uuid.UUID,
        rule_code: str,
        entity_name: str,
    ) -> Optional[DecisionMemory]:
        """
        Finds an active decision memory strictly scoped to the tenant company.
        """
        stmt = (
            select(DecisionMemory)
            .where(
                (DecisionMemory.company_id == company_id)
                & (DecisionMemory.rule_code == rule_code)
                & (DecisionMemory.entity_name == entity_name)
                & (DecisionMemory.is_active.is_(True))
            )
            .order_by(DecisionMemory.created_at.desc())
        )
        return db.scalars(stmt).first()
