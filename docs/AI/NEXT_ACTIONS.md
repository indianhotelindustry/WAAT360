# NEXT ACTIONS — WAAST360 Prioritized Backlog

This backlog defines the exact, prioritized execution sequence for incoming engineers and AI agents.

---

## Priority Scale
- **P0**: Critical path / immediate next execution item.
- **P1**: High priority (completes the core Golden Path vertical slice).
- **P2**: Normal priority (polish, edge cases, error resilience).
- **P3**: Future Prime capabilities (deferred from Lite).

---

## Completed Tasks (Phases 3A – 3L, Phase 5, Phase 6)

- [x] **[P0] TASK-GP-01: Document Ingestion & Storage Foundation** (`POST /api/v1/documents/upload`, SHA256 checksum, duplicate detection).
- [x] **[P0] TASK-GP-02: AI Provider Abstraction & Gemini Implementation** (`AIProvider`, `GeminiProvider`, `POST /api/v1/documents/{id}/extract`).
- [x] **[P1] TASK-GP-03: Structured Accounting Proposal & Deterministic Rules Validation** (`ProposalEngine`, `ValidationEngine`, `VAL-RULE-001`, `VAL-RULE-002`, `VAL-RULE-003`).
- [x] **[P1] TASK-GP-04: Multi-Step Human Approval Workflow** (`POST /api/v1/proposals/{id}/approve`, authoritative `Transaction`, `TransactionLine`s, `PostingJob`).
- [x] **[P1] TASK-GP-05: Bridge Posting Execution & Read-Back Verification** (`TallySimulatedAdapter`, `PostingAttempt`, `PostingResponse`, `VerificationResult`, `AuditEvent`).
- [x] **[P1] TASK-GP-06: Golden Path Frontend UI Console** (Next.js 16 interactive dashboard with 10-stage pipeline, invoice ingestion, approval console, and forensic audit timeline).
- [x] **[P2] TASK-POL-01: Bridge Simulated Adapter CLI Flag** (`python src/main.py start --simulated`, `--simulated` flag on `test-tally` and `discover`).
- [x] **[P0] TASK-CMD-01: Enterprise Command Center & Real-Data Simulator** (Enterprise SaaS UI, real database KPI summary endpoint, simulator cycle execution via `TallySimulatedAdapter`, page reload persistence, `.env.example`).
- [x] **[P0] TASK-CMD-02: V0.0.01 Client Command Center Application Shell & Client Conviction Pass** (Configurable client branding, collapsible enterprise sidebar, top header, 68px global Control Flow sub-header, 6 Command Center tabs, real DB KPIs, Attention Required section, honest standby states, DEMO MODE safety).
- [x] **[P0] TASK-KNOW-01: Knowledge Core with Provenance** (`KnowledgeItem` FACT/RULE/RECOMMENDATION/DECISION, authoritative source, jurisdiction, effective dates, rule version, status — migration `214dbe10b9e5`).
- [x] **[P0] TASK-KNOW-02: Decision Memory & Forensic Transparency** (`DecisionMemory` per company+finding_type, `KNOWN_EXCEPTION` surfacing, multi-tenant isolation).
- [x] **[P0] TASK-HEALTH-01: Accounting Health Check Scanner** (`POST /api/v1/health-check/{company_id}/scan`, provenance-backed findings, "Why This Was Flagged" explanations, FACT/RULE/RECOMMENDATION/DECISION segregation).
- [x] **[P0] TASK-HEALTH-02: Correction Proposal Lifecycle** (7-step status machine `PROPOSED→ARCHIVED`, stale-proposal protection via 409 CONFLICT, idempotent, auditable, actor-bound).
- [x] **[P1] TASK-TALLY-01: Extended TallyAdapter Contract** (`getLedger`, `updateLedgerMaster`, `verifyLedgerMaster` in base + `TallySimulatedAdapter`).
- [x] **[P0] TASK-UI-01: Lite Enterprise Theme** (White/light workspace, dark typography, green/amber/red states, high-density tables, professional accounting ERP appearance).
- [x] **[P0] TASK-UI-02: Company Intelligence View** (`CompanyIntelligenceView.tsx` — health dashboard, forensic finding cards, correction workflow, decision memory recording, per-company tenant isolation).

---

## Next Backlog Queue

### [P0] TASK-DEP-01: Client Deployment & Office Machine Installer
- **Why**: Prepare the Bridge distribution bundle for installation on the client's Windows office machine where live TallyPrime is hosted.
- **Expected Files**:
  - `bridge/scripts/install_service.ps1`: Windows Service installation script for unattended background operation.
  - `bridge/scripts/run_bridge.bat`: Quick-start launcher.
- **Acceptance Criteria**:
  - Standalone execution on Windows 10/11/Server.
  - Configures `BRIDGE_API_KEY` and points outbound to Cloud API.

---

### [P0] TASK-CERT-01: LIVE-TALLY-CERT-001 Live Execution
- **Why**: Deployment certification gate on the client's office machine.
- **Location**: Client Office Machine (running live TallyPrime on `localhost:9000`).
- **Dependencies**: TASK-DEP-01.
- **Acceptance Criteria**:
  - Satisfy all 5 gates in [`docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md):
    1. Connectivity to port 9000.
    2. Company discovery returns real active company.
    3. Master extraction reads live ledgers.
    4. Test purchase voucher posted to real Tally.
    5. Read-back verification confirms voucher in Tally Daybook.

---

### [P1] TASK-POL-02: Multi-Page PDF Invoice Ingestion
- **Why**: Handle complex multi-page invoices with tables spanning several pages.
- **Expected Files**: `api/src/ai/gemini_provider.py`.
- **Dependencies**: TASK-GP-02.
