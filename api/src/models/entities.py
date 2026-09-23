import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    generate_uuid7,
    utc_now,
)

# JSONVariant: In PostgreSQL uses native JSONB; in testing / SQLite falls back to JSON
JSONVariant = JSON().with_variant(JSONB, "postgresql")

# ==========================================
# 1. TENANT & RBAC CLUSTER
# ==========================================


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    companies: Mapped[list["Company"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Company(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    financial_year_start: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="companies")
    branches: Mapped[list["Branch"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    tally_companies: Mapped[list["TallyCompany"]] = relationship(back_populates="company")

    __table_args__ = (Index("ix_companies_org_active", "organization_id", "is_deleted"),)


class Branch(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    branch_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    state_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="branches")

    __table_args__ = (
        UniqueConstraint("company_id", "branch_code", name="uq_company_branch_code"),
        Index("ix_branches_org_company", "organization_id", "company_id"),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship()


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )

    role: Mapped["Role"] = relationship(back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship()


# ==========================================
# 2. TALLY & BRIDGE CLUSTER
# ==========================================


class TallyInstance(Base, TimestampMixin):
    """
    Target Tally runtime.
    Distinct from WAAST360 Company and Bridge agent.
    """

    __tablename__ = "tally_instances"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    instance_name: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), default="127.0.0.1", nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=9000, nullable=False)
    tally_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tally_companies: Mapped[list["TallyCompany"]] = relationship(
        back_populates="tally_instance", cascade="all, delete-orphan"
    )
    bridges: Mapped[list["Bridge"]] = relationship(back_populates="tally_instance")


class TallyCompany(Base, TimestampMixin):
    """
    Explicit entity representing a distinct company registered inside a Tally Instance.
    Preserves actual Tally company identity and discovery metadata.
    """

    __tablename__ = "tally_companies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    tally_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tally_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tally_guid: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    financial_year: Mapped[str | None] = mapped_column(String(50), nullable=True)
    books_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="DISCOVERED", nullable=False)
    company_metadata: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)

    tally_instance: Mapped["TallyInstance"] = relationship(back_populates="tally_companies")
    company: Mapped[Optional["Company"]] = relationship(back_populates="tally_companies")

    __table_args__ = (
        UniqueConstraint("tally_instance_id", "tally_guid", name="uq_tally_instance_guid"),
    )


class Bridge(Base, TimestampMixin):
    """
    Local execution/transport agent.
    Conceptual relationship: BRIDGE -> connects to -> TALLY_INSTANCE.
    """

    __tablename__ = "bridges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tally_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tally_instances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bridge_client_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    os_platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="OFFLINE", nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tally_instance: Mapped[Optional["TallyInstance"]] = relationship(back_populates="bridges")
    connections: Mapped[list["Connection"]] = relationship(
        back_populates="bridge", cascade="all, delete-orphan"
    )


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    bridge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bridges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disconnect_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    bridge: Mapped["Bridge"] = relationship(back_populates="connections")


class SyncJob(Base, TimestampMixin):
    __tablename__ = "sync_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tally_company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tally_companies.id", ondelete="SET NULL"), nullable=True
    )
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(50), nullable=True)

    sync_runs: Mapped[list["SyncRun"]] = relationship(
        back_populates="sync_job", cascade="all, delete-orphan"
    )


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    sync_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_pulled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="RUNNING", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    sync_job: Mapped["SyncJob"] = relationship(back_populates="sync_runs")


# ==========================================
# 3. MASTER DATA CLUSTER
# ==========================================


class Party(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "parties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tally_company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tally_companies.id", ondelete="SET NULL"), nullable=True
    )
    tally_guid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tally_master_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    party_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CREDITOR, DEBTOR
    parent_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    identities: Mapped[list["PartyIdentity"]] = relationship(
        back_populates="party", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_parties_tenant", "organization_id", "company_id", "name"),)


class PartyIdentity(Base, TimestampMixin):
    __tablename__ = "party_identities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    party_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gstin: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    pan: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    state_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registration_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(Text, nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)

    party: Mapped["Party"] = relationship(back_populates="identities")


class Ledger(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ledgers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tally_company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tally_companies.id", ondelete="SET NULL"), nullable=True
    )
    tally_guid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tally_master_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)

    __table_args__ = (Index("ix_ledgers_tenant", "organization_id", "company_id", "name"),)


class Item(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tally_company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tally_companies.id", ondelete="SET NULL"), nullable=True
    )
    tally_guid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tally_master_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hsn_sac_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    uom: Mapped[str | None] = mapped_column(String(50), nullable=True)

    __table_args__ = (Index("ix_items_tenant", "organization_id", "company_id", "name"),)


class Tax(Base, TimestampMixin):
    __tablename__ = "taxes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CGST, SGST, IGST, TDS, TCS
    rate_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    ledger_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledgers.id", ondelete="SET NULL"), nullable=True
    )


# ==========================================
# 4. DOCUMENT INGESTION & AI CLUSTER
# ==========================================


class Document(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="UPLOADED", nullable=False)

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_documents_tenant_status", "organization_id", "company_id", "status"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="versions")
    extractions: Mapped[list["DocumentExtraction"]] = relationship(
        back_populates="document_version", cascade="all, delete-orphan"
    )


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # GeminiProvider, ClaudeProvider
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_response_json: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    document_version: Mapped["DocumentVersion"] = relationship(back_populates="extractions")
    fields: Mapped[list["ExtractionField"]] = relationship(
        back_populates="extraction", cascade="all, delete-orphan"
    )


class ExtractionField(Base):
    __tablename__ = "extraction_fields"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    document_extraction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_extractions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    bounding_box: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    extraction: Mapped["DocumentExtraction"] = relationship(back_populates="fields")


# ==========================================
# 5. ACCOUNTING PROPOSAL & APPROVAL CLUSTER
# ==========================================


class AccountingProposal(Base, TimestampMixin, SoftDeleteMixin):
    """
    Tentative, AI-generated accounting entry.
    Kept separate from authoritative Transaction records.
    """

    __tablename__ = "accounting_proposals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_extraction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_extractions.id", ondelete="SET NULL"), nullable=True
    )
    voucher_type: Mapped[str] = mapped_column(String(50), nullable=False)
    proposed_date: Mapped[date] = mapped_column(Date, nullable=False)
    party_ledger_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ledgers.id", ondelete="SET NULL"), nullable=True
    )
    total_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 4), default=0.0, nullable=False)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False)

    validations: Mapped[list["ValidationResult"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_proposals_tenant_status", "organization_id", "company_id", "status"),
    )


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    accounting_proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # INFO, WARNING, ERROR, BLOCKER
    is_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    proposal: Mapped["AccountingProposal"] = relationship(back_populates="validations")


class Approval(Base):
    """
    Approval entity designed to support future multi-step approval workflows without redesign.
    """

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    accounting_proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_proposals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # APPROVED, REJECTED, MODIFIED_AND_APPROVED
    decision_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_step: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )  # Multi-step sequence support
    authority_context: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Context e.g. "FINANCE_HEAD", "PRIMARY_APPROVER"
    approval_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)

    proposal: Mapped["AccountingProposal"] = relationship(back_populates="approvals")
    user: Mapped["User"] = relationship()


# ==========================================
# 6. TRANSACTION & POSTING CLUSTER
# ==========================================


class Transaction(Base, TimestampMixin):
    """
    Authoritative Accounting Transaction created only upon Approval.
    No casual deletion; immutable accounting record.
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    accounting_proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_proposals.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    voucher_type: Mapped[str] = mapped_column(String(50), nullable=False)
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    narration: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["TransactionLine"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    posting_jobs: Mapped[list["PostingJob"]] = relationship(back_populates="transaction")


class TransactionLine(Base):
    __tablename__ = "transaction_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ledger_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledgers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_debit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"), nullable=True
    )
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    rate: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    transaction: Mapped["Transaction"] = relationship(back_populates="lines")


class PostingJob(Base, TimestampMixin):
    __tablename__ = "posting_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    bridge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bridges.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="QUEUED", nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transaction: Mapped["Transaction"] = relationship(back_populates="posting_jobs")
    attempts: Mapped[list["PostingAttempt"]] = relationship(
        back_populates="posting_job", cascade="all, delete-orphan"
    )


class PostingAttempt(Base):
    __tablename__ = "posting_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    posting_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posting_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_format: Mapped[str] = mapped_column(String(20), default="XML", nullable=False)
    payload_sent: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    posting_job: Mapped["PostingJob"] = relationship(back_populates="attempts")
    responses: Mapped[list["PostingResponse"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class PostingResponse(Base):
    __tablename__ = "posting_responses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    posting_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posting_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_response: Mapped[str] = mapped_column(Text, nullable=False)
    tally_voucher_guid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tally_master_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tally_voucher_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    attempt: Mapped["PostingAttempt"] = relationship(back_populates="responses")
    verifications: Mapped[list["VerificationResult"]] = relationship(
        back_populates="posting_response", cascade="all, delete-orphan"
    )


class VerificationResult(Base):
    """
    Preserves comprehensive forensic evidence of read-back verification against Tally.
    """

    __tablename__ = "verification_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    posting_response_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("posting_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expected_voucher_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actual_tally_voucher_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tally_guid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    expected_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    actual_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    expected_accounting_identity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actual_accounting_identity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_method: Mapped[str] = mapped_column(
        String(50), default="TALLY_READ_BACK", nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # VERIFIED, MISMATCH, FAILED
    mismatch_details: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    posting_response: Mapped["PostingResponse"] = relationship(back_populates="verifications")


# ==========================================
# 7. EXCEPTIONS & AUDIT CLUSTER
# ==========================================


class DomainException(Base):
    __tablename__ = "domain_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    exception_category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="ERROR", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AuditEvent(Base):
    """
    Append-only immutable audit trail.
    Every major state transition, approval, posting, and archive event is logged here.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # USER, AI_AGENT, BRIDGE, SYSTEM_RULE
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    changes: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    __table_args__ = (Index("ix_audit_org_action", "organization_id", "action", "recorded_at"),)


# ==========================================
# 11. KNOWLEDGE CORE & HEALTH CHECK CLUSTER
# ==========================================
from src.models.knowledge_entities import (  # noqa: E402
    CompanyKnowledgeProfile,
    CorrectionJob,
    CorrectionProposal,
    DecisionMemory,
    ForensicFinding,
    ForensicScan,
    KnowledgeItem,
    KnowledgeSource,
)

__all__ = [
    "Organization",
    "Company",
    "Branch",
    "User",
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "TallyInstance",
    "TallyCompany",
    "Bridge",
    "Connection",
    "SyncJob",
    "SyncRun",
    "Party",
    "PartyIdentity",
    "Ledger",
    "Item",
    "Tax",
    "Document",
    "DocumentVersion",
    "DocumentExtraction",
    "ExtractionField",
    "AccountingProposal",
    "ValidationResult",
    "Approval",
    "Transaction",
    "TransactionLine",
    "PostingJob",
    "PostingAttempt",
    "PostingResponse",
    "VerificationResult",
    "DomainException",
    "AuditEvent",
    # Knowledge Core & Forensic Health Check
    "KnowledgeSource",
    "KnowledgeItem",
    "CompanyKnowledgeProfile",
    "DecisionMemory",
    "ForensicScan",
    "ForensicFinding",
    "CorrectionProposal",
    "CorrectionJob",
]
