import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, generate_uuid7, utc_now
from src.models.entities import JSONVariant

# =========================================================================
# WAAST360 KNOWLEDGE CORE & ACCOUNTING HEALTH CHECK DOMAIN ENTITIES
# =========================================================================


class KnowledgeSource(Base, TimestampMixin):
    """
    Authoritative provenance tracking for accounting, tax, and Tally knowledge.
    Separates official/verified knowledge from derived rules or LLM explanations.
    """

    __tablename__ = "knowledge_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    source_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    authority_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # OFFICIAL_AUTHORITATIVE, VERIFIED_WAAST_KNOWLEDGE, DERIVED_RULE, AI_EXPLANATION, HUMAN_DECISION
    reference_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    citation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String(10), default="IN", nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    items: Mapped[list["KnowledgeItem"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class KnowledgeItem(Base, TimestampMixin):
    """
    Version-sensitive, date-bound institutional knowledge item.
    Supports temporal validity (effective_from, effective_until) and Tally version mapping.
    """

    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    knowledge_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # TALLY, ACCOUNTING, GST_TAX, TDS_TCS, AUDIT_CONTROL, FORENSIC_RULES, COMPANY_KNOWLEDGE, DECISION_MEMORY
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    jurisdiction: Mapped[str] = mapped_column(String(10), default="IN", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rule_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tally_version_pattern: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="ACTIVE", nullable=False, index=True
    )  # ACTIVE, DEPRECATED, DRAFT
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=1.00, nullable=False)

    # Relationships
    source: Mapped["KnowledgeSource"] = relationship(back_populates="items")


class CompanyKnowledgeProfile(Base, TimestampMixin):
    """
    Normalized company accounting knowledge profile anchor.
    Does NOT duplicate Tally master data; acts as context anchor for policies and exceptions.
    """

    __tablename__ = "company_knowledge_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True
    )
    accounting_policy_references: Mapped[dict] = mapped_column(
        JSONVariant, default=dict, nullable=False
    )
    gst_jurisdiction_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    industry_sector: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DecisionMemory(Base, TimestampMixin):
    """
    Audited human decision record when an authorized accountant reviews a finding
    and confirms an intentional accounting treatment or policy exception.
    Does NOT blind-suppress rules; converts them to transparent Known Exceptions.
    """

    __tablename__ = "decision_memories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    finding_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # LEDGER, GROUP, TAX_RATE
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    current_state: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    recommended_state: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    human_decision: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # INTENTIONAL_OVERRIDE, KNOWN_EXCEPTION
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(50), default="CONTROLLER", nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    findings: Mapped[list["ForensicFinding"]] = relationship(
        back_populates="known_exception", cascade="all"
    )


class ForensicScan(Base, TimestampMixin):
    """
    Execution header for a company-wide Accounting Health Check forensic review.
    """

    __tablename__ = "forensic_scans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tally_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("tally_companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scan_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    scan_status: Mapped[str] = mapped_column(
        String(30), default="COMPLETED", nullable=False, index=True
    )  # RUNNING, COMPLETED, FAILED
    ledgers_reviewed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_recommended_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    healthy_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gst_findings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_clusters_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    known_exceptions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overall_health: Mapped[str] = mapped_column(
        String(30), default="HEALTHY", nullable=False, index=True
    )  # HEALTHY, REVIEW_RECOMMENDED, CRITICAL_FINDINGS
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    findings: Mapped[list["ForensicFinding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class ForensicFinding(Base, TimestampMixin):
    """
    Evidence-backed individual finding.
    Strictly separates: FACT, RULE, RECOMMENDATION, DECISION.
    """

    __tablename__ = "forensic_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forensic_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    finding_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # LEDGER, GROUP, TAX_CONFIG, PARTY
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # HEALTHY, REVIEW_RECOMMENDED, CRITICAL

    # The 4 Separations:
    fact_observed: Mapped[str] = mapped_column(Text, nullable=False)
    fact_details: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    rule_triggered: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    decision_status: Mapped[str] = mapped_column(
        String(30), default="PENDING_REVIEW", nullable=False, index=True
    )  # PENDING_REVIEW, KNOWN_EXCEPTION, PROPOSED_CORRECTION, CORRECTED, RESOLVED

    # If this matches a known decision memory
    known_exception_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("decision_memories.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    scan: Mapped["ForensicScan"] = relationship(back_populates="findings")
    known_exception: Mapped[Optional["DecisionMemory"]] = relationship(back_populates="findings")
    corrections: Mapped[list["CorrectionProposal"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class CorrectionProposal(Base, TimestampMixin):
    """
    Controlled correction proposal remediation for a forensic finding.
    Enforces strict lifecycle: PROPOSED -> APPROVAL_REQUIRED -> APPROVED -> EXECUTION_ELIGIBLE -> BRIDGE_EXECUTION -> VERIFIED.
    Protects against stale proposals if Tally state changed.
    """

    __tablename__ = "correction_proposals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forensic_findings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # LEDGER, GROUP
    target_entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_tally_guid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    before_state: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    proposed_state: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="PROPOSED", nullable=False, index=True
    )  # PROPOSED, APPROVAL_REQUIRED, APPROVED, EXECUTION_ELIGIBLE, EXECUTED, VERIFIED, REJECTED, STALE_REJECTED
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stale_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    finding: Mapped["ForensicFinding"] = relationship(back_populates="corrections")
    jobs: Mapped[list["CorrectionJob"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class CorrectionJob(Base, TimestampMixin):
    """
    Outbound bridge execution job for a verified master correction in Tally.
    Records before-and-after state and read-back verification evidence.
    """

    __tablename__ = "correction_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("correction_proposals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    job_status: Mapped[str] = mapped_column(
        String(30), default="QUEUED", nullable=False, index=True
    )  # QUEUED, IN_PROGRESS, SUCCESS, FAILED
    execution_actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    target_state_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    before_state_captured: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    after_state_captured: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    read_back_evidence: Mapped[dict] = mapped_column(JSONVariant, default=dict, nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    proposal: Mapped["CorrectionProposal"] = relationship(back_populates="jobs")
