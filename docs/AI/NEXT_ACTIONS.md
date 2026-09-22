# NEXT ACTIONS — WAAST360 Prioritized Backlog

This backlog defines the exact, prioritized execution sequence for incoming engineers and AI agents.

---

## Priority Scale
- **P0**: Critical path / immediate next execution item.
- **P1**: High priority (completes the core Golden Path vertical slice).
- **P2**: Normal priority (polish, edge cases, error resilience).
- **P3**: Future Prime capabilities (deferred from Lite).

---

## Backlog Queue

### [P0] TASK-GP-01: Document Ingestion & Storage Foundation
- **Why**: The Lite Golden Path requires users to upload invoices (PDF, PNG, JPG) before AI extraction can operate.
- **Expected Files**:
  - `api/src/routers/documents.py`: Endpoints for `POST /api/v1/documents/upload` and `GET /api/v1/documents`.
  - `api/src/services/storage_service.py`: Local secure file persistence (uploads directory) and hash computation.
- **Dependencies**: Uses existing `Document` and `DocumentVersion` entities in `api/src/models/entities.py`.
- **Acceptance Criteria**:
  - Uploading a PDF or image creates a `Document` record in PostgreSQL with SHA256 checksum and MIME type.
  - Generates initial `DocumentVersion` with file path and status `UPLOADED`.
- **Verification Method**: `pytest tests/test_documents_router.py`.

---

### [P0] TASK-GP-02: AI Provider Abstraction & Gemini Implementation
- **Why**: Standardizes AI extraction behind an interface, enabling Gemini as the primary provider with mock fallbacks for testing.
- **Expected Files**:
  - `api/src/ai/base.py`: Abstract base class `AIProvider` defining `extract_invoice(...) -> ExtractedInvoice`.
  - `api/src/ai/gemini_provider.py`: Concrete `GeminiProvider` using Google Gemini structured schema.
  - `api/src/ai/models.py`: Pydantic models (`ExtractedInvoice`, `InvoiceLineItem`, `TaxDetails`).
  - `api/src/routers/documents.py`: Endpoint `POST /api/v1/documents/{id}/extract`.
- **Dependencies**: TASK-GP-01.
- **Acceptance Criteria**:
  - Extracts vendor name, invoice number, date, line items, taxable amount, CGST, SGST, IGST, total.
  - Persists results into `DocumentExtraction` and `ExtractionField` records.
  - Falls back gracefully to deterministic offline extraction if `GEMINI_API_KEY` is not present.
- **Verification Method**: `pytest tests/test_ai_provider.py`.

---

### [P1] TASK-GP-03: Structured Accounting Proposal & Rules Validation Engine
- **Why**: AI proposals cannot be posted directly; they must be converted into double-entry accounting and verified by validation rules.
- **Expected Files**:
  - `api/src/services/proposal_engine.py`: Converts `DocumentExtraction` into double-entry ledger lines.
  - `api/src/services/validation_engine.py`: Runs mathematical and accounting rule checks.
  - `api/src/routers/proposals.py`: Endpoints `POST /api/v1/documents/{id}/proposals` and `GET /api/v1/proposals`.
- **Dependencies**: TASK-GP-02.
- **Acceptance Criteria**:
  - Automatically balances debits and credits ($\sum \text{Debits} == \sum \text{Credits}$).
  - Verifies GST calculations against taxable values.
  - Creates `AccountingProposal` and `ValidationResult` in PostgreSQL.
- **Verification Method**: `pytest tests/test_proposal_engine.py`.

---

### [P1] TASK-GP-04: Multi-Step Human Approval Workflow
- **Why**: Enforces product constitution principle: "Human approves" before financial posting.
- **Expected Files**:
  - `api/src/routers/approvals.py`: Endpoints for `POST /api/v1/proposals/{id}/approve` and `POST /api/v1/proposals/{id}/reject`.
- **Dependencies**: TASK-GP-03.
- **Acceptance Criteria**:
  - Creates `Approval` record with decision (`APPROVED` / `REJECTED`), approver ID, timestamp, and notes.
  - On approval, creates a `PostingJob` in PostgreSQL with status `PENDING` ready for Bridge polling.
- **Verification Method**: `pytest tests/test_approvals.py`.

---

### [P1] TASK-GP-05: Bridge Posting Execution & Read-Back Verification
- **Why**: Completes the bridge-to-Tally leg of the Golden Path.
- **Expected Files**:
  - `bridge/src/adapters/simulated_adapter.py`: Simulated TallyAdapter for local testing without physical Tally.
  - `bridge/src/engine/reconciler.py`: Executes `create_voucher` and `verify_transaction`.
  - `api/src/routers/bridge.py`: Records `PostingAttempt` and `VerificationResult`.
- **Dependencies**: TASK-GP-04.
- **Acceptance Criteria**:
  - Bridge polls pending job $\rightarrow$ posts voucher $\rightarrow$ immediately queries Tally to verify existence and amount $\rightarrow$ submits evidence to Cloud API.
  - Cloud API creates `VerificationResult` and immutable `AuditEvent`.
- **Verification Method**: End-to-end integration test in `api/tests/test_golden_path.py`.

---

### [P1] TASK-GP-06: Golden Path Frontend UI Console
- **Why**: Allows non-technical users to experience the complete Golden Path in Next.js.
- **Expected Files**:
  - `web/src/app/page.tsx` (or tabbed subpages under `web/src/app/invoices/`).
- **Dependencies**: TASK-GP-01 through TASK-GP-05.
- **Acceptance Criteria**:
  - UI supports file drop $\rightarrow$ view extracted fields $\rightarrow$ review proposed voucher lines $\rightarrow$ click "Approve & Post" $\rightarrow$ real-time posting badge and audit proof timeline.
- **Verification Method**: `npm run lint` and manual browser walkthrough.

---

### [P2] TASK-POL-01: Bridge Simulated Adapter CLI Flag
- **Why**: Allows seamless local demonstration when running `python bridge/src/main.py start --simulated`.
- **Expected Files**: `bridge/src/main.py`, `bridge/src/adapters/factory.py`.
- **Acceptance Criteria**: Running with `--simulated` loads `TallySimulatedAdapter` with sample Indian GST ledgers.
- **Verification Method**: `python bridge/src/main.py test-tally --simulated` returns `Online: True`.

---

### [P3] TASK-GATE-01: Deployment-Time Live Tally Certification Gate
- **Why**: Formal sign-off on the client's office machine with real TallyPrime.
- **Documentation**: [`docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md).
- **Dependencies**: Access to client office machine.
- **Acceptance Criteria**: All 4 steps of `LIVE-TALLY-CERT-001` pass against running TallyPrime on port 9000.
