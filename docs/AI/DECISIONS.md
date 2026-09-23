# Architectural Decision Records (ADRs) — WAAST360

This document tracks all locked, active, and foundational architectural decisions.

---

### DEC-001: Product Identity & Name
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: The product name is **WAAST360** (*Wise Accounting Automation System for Tally*).
- **Rationale**: Clean, authoritative, and distinctive accounting automation brand.
- **Implication**: All repositories, documentation, and services use WAAST360 naming.

---

### DEC-002: Phased Delivery Strategy
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Strategy is **Perfect Planning → Strong Foundation → WAAST360 Lite → WAAST360 Prime**.
- **Rationale**: Immediate commercial delivery of Lite (3–5 days) without compromising long-term platform capability.
- **Implication**: Focus on the Lite Golden Path vertical slice while building on an enterprise-grade schema.

---

### DEC-003: No Throwaway Lite Architecture
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Lite must be implemented on the Prime-grade domain and database model, not as a throwaway MVP.
- **Rationale**: Throwaway MVPs require complete rewrites; Prime-grade foundations allow feature flags and modular scaling.
- **Implication**: Full 34-table domain model is implemented and active from day one.

---

### DEC-004: Tally as the Authoritative System of Record
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Tally remains the sole accounting system of record. WAAST360 is the control, intelligence, and orchestration layer.
- **Rationale**: Clients rely on Tally for tax filings, statutory audits, and existing accounting workflows.
- **Implication**: WAAST360 does not replace Tally balances; it orchestrates and verifies postings in Tally.

---

### DEC-005: Core Accounting Automation Principle
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**:
  $$\text{AI proposes} \rightarrow \text{Rules validate} \rightarrow \text{Human approves} \rightarrow \text{Bridge posts} \rightarrow \text{Tally records} \rightarrow \text{WAAST360 verifies} \rightarrow \text{Audit proves}$$
- **Rationale**: Guarantees accounting safety, regulatory compliance, and total auditability.
- **Implication**: AI suggestions never post automatically without validation and human approval.

---

### DEC-006: Strict Separation of Tenant & Tally Entities
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Strictly distinguish:
  $$\text{WAAST360 Company} \ne \text{Tally Instance} \ne \text{Tally Company} \ne \text{Bridge}$$
- **Rationale**: One Tally instance can host multiple Tally companies; one organization may map multiple Tally companies to different internal accounting companies.
- **Implication**: Each concept has its own dedicated database table and relationships.

---

### DEC-007: TallyCompany as a First-Class Entity
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: `TallyCompany` is an explicit domain entity storing native Tally metadata (`tally_guid`, `company_name`, `financial_year`, `books_from`, `last_seen_at`, `status`).
- **Rationale**: Preserves Tally's native identity independently of internal WAAST360 UUIDs.
- **Implication**: Bridge discovers `TallyCompany`; user explicitly maps it to a WAAST360 `Company`.

---

### DEC-008: Standalone Windows Bridge Agent
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: The Bridge is a standalone Python client installed on the Windows machine where TallyPrime resides.
- **Rationale**: Tally operates over local loopback HTTP (`localhost:9000`); cloud cannot and must not reach into local private networks directly.
- **Implication**: Bridge runs locally on Windows, isolated from Cloud API infrastructure.

---

### DEC-009: Outbound-Initiated Secure Bridge Channel
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: The Bridge initiates all connections outbound to WAAST360 Cloud via HTTPS polling.
- **Rationale**: Opening inbound ports on customer firewalls is insecure and administratively complex.
- **Implication**: Tally port 9000 is never exposed to the public internet.

---

### DEC-010: Capability-Based Tally Adapters
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Tally communication is encapsulated behind `TallyAdapter` reporting `TallyCapabilities`.
- **Rationale**: Different Tally versions (TallyPrime 7.0+ vs 4.x vs ERP 9) support different capabilities (JSON vs XML).
- **Implication**: Core business logic interacts only with the abstract adapter interface.

---

### DEC-011: JSON-First with XML Compatibility Fallback
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Prefer `TallyJsonAdapter` where supported by TallyPrime, falling back to `TallyXmlAdapter` with `<SVCURRENTCOMPANY>` envelopes.
- **Rationale**: Native JSON reduces parsing overhead, while XML ensures compatibility across older Tally versions.
- **Implication**: Adapter factory auto-detects capabilities and selects the optimal adapter.

---

### DEC-012: TDL Not Mandatory for Lite
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Lite operates using standard Tally HTTP/XML/JSON interfaces without requiring custom TDL definitions.
- **Rationale**: Zero-deployment overhead on customer Tally instances for Lite. Custom TDL can be introduced in Prime.
- **Implication**: All data queries use standard collection definitions and export forms.

---

### DEC-013: Durable Offline Queue in Bridge
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: The Bridge maintains a local SQLite store (`BridgeLocalStore`) for offline job buffering and idempotency logging.
- **Rationale**: Prevents job loss during intermittent internet disconnection.
- **Implication**: Jobs are queued locally and executed with state tracking.

---

### DEC-014: Non-Destructive Soft Deletion
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Financial and domain entities use `SoftDeleteMixin` (`is_deleted`, `deleted_at`, `deleted_by`, `deletion_reason`).
- **Rationale**: Regulatory accounting compliance prohibits hard-deleting transactions, ledger accounts, or vouchers.
- **Implication**: Deletions are audited flags; physical rows are preserved.

---

### DEC-015: Multi-Step Approval Model
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: `AccountingProposal` separates proposals from approved `Transaction` entities, supporting multi-step `Approval` records.
- **Rationale**: Enterprise accounting often requires maker-checker or multi-tiered approval workflows.
- **Implication**: Approvals are tracked independently from proposals and transactions.

---

### DEC-016: Read-Back Verification Evidence
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Post-operation read-back verification captures verifiable evidence in `VerificationResult` (`actual_voucher_number`, `actual_guid`, `actual_amount`, `mismatch_details`).
- **Rationale**: Blindly trusting HTTP 200 responses risks silent posting failures or misallocated ledgers.
- **Implication**: Verification queries Tally directly to confirm the transaction exists as expected.

---

### DEC-017: Strict Separation of Live Tally Certification vs Simulation
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Simulated adapter testing is recognized for developer velocity, but live Tally certification is gated separately under `LIVE-TALLY-CERT-001`.
- **Rationale**: Faking live certification undermines client trust and masks real Tally quirks.
- **Implication**: Local tests pass via simulated adapters; live certification is executed on the client machine.

---

### DEC-018: UUIDv7 Primary Keys
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Internal database primary keys use time-ordered UUIDv7 (generated natively via Python 3.14 `uuid.uuid7()`).
- **Rationale**: Combines the distributed creation benefits of UUIDs with the B-tree indexing performance of sequential IDs.
- **Implication**: Sequential integer IDs are not used as domain primary keys.

---

### DEC-019: TallySimulatedAdapter Contract Fidelity & Realistic GST State
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: `TallySimulatedAdapter` implements the exact identical `TallyAdapter` abstract interface with zero special shortcuts. It maintains realistic Indian GST accounting state (Purchase A/c, CGST 9%, SGST 9%, IGST 18%, Creditors, Debtors), sequential voucher numbers (`PUR/2026/0001`), and idempotent deduplication.
- **Rationale**: Allows developer iteration and automated end-to-end integration testing without creating a second shortcut architecture for demos.
- **Implication**: Switching between simulation and live Tally requires only changing the adapter instance at runtime.

---

### DEC-020: Deterministic Rules Engine Preceding Approval
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: AI extraction output must pass deterministic accounting validation rules (`VAL-RULE-001` double-entry balance, `VAL-RULE-002` GST math invariant, `VAL-RULE-003` duplicate reference detection) and explicit human approval before any transaction or posting job is materialized.
- **Rationale**: Eliminates AI hallucination risks in statutory double-entry accounting.
- **Implication**: AI proposes; rules validate; human approves; only approved proposals materialize into immutable transactions.

---

### DEC-021: Provider-Agnostic AI Extraction Layer
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: AI invoice extraction is encapsulated behind `AIProvider` (`src.ai.base`), with `GeminiProvider` as the primary implementation and a deterministic fallback when offline or lacking API keys.
- **Rationale**: Prevents vendor lock-in to Gemini and enables easy pluggability for other models (Claude, local OCR) in future Prime releases.
- **Implication**: Core application code interacts only with `AIProvider.extract_invoice()`.

---

### DEC-022: Explicit 10-Stage Lifecycle State Machine
- **Status**: LOCKED
- **Date**: 2026-09-22
- **Decision**: Every document in the Golden Path traverses explicit states:
  $$\text{RECEIVED} \rightarrow \text{EXTRACTED} \rightarrow \text{PROPOSED} \rightarrow \text{VALIDATED} \rightarrow \text{PENDING\_APPROVAL} \rightarrow \text{APPROVED} \rightarrow \text{POSTING} \rightarrow \text{POSTED} \rightarrow \text{VERIFIED}$$
- **Rationale**: Full traceability across automated and human gates; failure states (`DUPLICATE_FLAGGED`, `VALIDATION_FAILED`, `REJECTED`) are strictly distinguished.
- **Implication**: API endpoints, database status columns, and frontend UI visualizer adhere to this exact state progression.

---

### DEC-023: Client Demo Command Center & Authoritative Simulator Integrity
- **Status**: LOCKED
- **Date**: 2026-09-23
- **Decision**:
  1. Frontend presentation uses an enterprise-grade Command Center UI (Deep Navy `#0F172A` navigation, clean SaaS body `#F8FAFC`, tailored financial typography).
  2. Simulator integrity: All simulation actions (`POST /api/v1/bridge/jobs/{id}/simulate-cycle`) execute strictly through the real `TallySimulatedAdapter` in the Bridge layer, writing `PostingAttempt`, `PostingResponse`, forensic `VerificationResult`, advancing state to `VERIFIED`, and appending immutable `AuditEvent`s. Zero client-side fake voucher strings or mock amounts are permitted.
  3. Authoritative KPIs: `GET /api/v1/dashboard/summary` computes metrics dynamically from authoritative PostgreSQL records (`Document`, `AccountingProposal`, `PostingJob`, `VerificationResult`, `DomainException`).
  4. Demo vs. Live transparency: 🟡 `DEMO MODE (Simulated Tally)` vs 🟢 `LIVE MODE (TallyPrime Connected)` is strictly derived from server runtime state and adapter classification.
  5. Persistence across refresh: REST query endpoints (`GET /documents/{id}/extraction`, enhanced `GET /proposals`) ensure complete workflow state reconstructs cleanly upon browser reload.
  6. Configurable API URL: Cloud dashboard relies on `NEXT_PUBLIC_API_BASE_URL` with `.env.example` contract.
- **Rationale**: Prevents demo falsification, proves system architecture to technical and executive stakeholders, and guarantees seamless transition from simulation to live TallyPrime on client office deployment.
- **Implication**: Both demo and production utilize identical database schemas, domain entities, and adapter contracts.

