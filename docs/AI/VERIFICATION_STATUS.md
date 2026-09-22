# VERIFICATION STATUS — WAAST360

This document records the factual verification matrix and ground truth evidence for WAAST360.

---

## 1. Verification Matrix

| Subsystem / Area | Category | Status | Evidence / Command Output |
| :--- | :--- | :---: | :--- |
| **PostgreSQL Database** | Integration | **PASS** | `alembic current` $\rightarrow$ `390eab233bf5 (head)`, 35 tables active in PostgreSQL 18.4 |
| **Cloud API Test Suite** | Integration | **PASS** | `pytest tests/` $\rightarrow$ 12 passed in 1.06s |
| **Bridge Test Suite** | Unit/Integration | **PASS** | `pytest tests/` $\rightarrow$ 16 passed in 0.39s |
| **Python Code Quality** | Quality Check | **PASS** | `ruff check src/ tests/` $\rightarrow$ All checks passed (API & Bridge) |
| **Frontend Lint** | Quality Check | **PASS** | `npm run lint` $\rightarrow$ ESLint 0 errors, 0 warnings |
| **Frontend Build** | Build Validation | **PASS** | `next build` $\rightarrow$ Compiled successfully in Turbopack, static routes generated |
| **Tally XML Adapter** | Unit Tested | **PASS** | Full envelope generation, parsing, `<SVCURRENTCOMPANY>` verified in tests |
| **Tally JSON Adapter** | Unit Tested | **PASS** | Native JSON payload and response parsing verified in tests |
| **Bridge Local Store** | Unit Tested | **PASS** | SQLite durable queue, idempotency history, and diagnostics verified in tests |
| **Posting Reconciler** | Unit Tested | **PASS** | Pre-check, posting, and post-check duplicate avoidance verified in tests |
| **Company Discovery Sync** | Integration | **PASS** | `test_companies_router.py` verifies discovery $\rightarrow$ PostgreSQL $\rightarrow$ mapping |
| **Live Tally Connectivity** | Live Host | **PENDING** | Port 9000 refused on dev laptop; requires client's office machine |
| **Live Company Discovery** | Live Host | **PENDING** | Gated under `LIVE-TALLY-CERT-001` |
| **Live Voucher Posting** | Live Host | **PENDING** | Gated under `LIVE-TALLY-CERT-001` |
| **Live Read-Back Verification**| Live Host | **PENDING** | Gated under `LIVE-TALLY-CERT-001` |

---

## 2. Category Definitions (Strictly Non-Interchangeable)
- **UNIT TESTED**: Verified in isolated memory with mocked dependencies.
- **INTEGRATION TESTED**: Verified across real interconnected subsystems (e.g. FastAPI talking to PostgreSQL).
- **LIVE VERIFIED**: Tested against live external runtime (e.g. running TallyPrime on port 9000).
- **CERTIFIED**: Formally validated against acceptance gate criteria on customer production environment.

---

## 3. Actual Command Verification Logs

### A. Database Verification
```powershell
# Command:
.\.venv\Scripts\alembic current
# Output:
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
390eab233bf5 (head)

# Python SQLAlchemy Inspector:
PG Version: PostgreSQL 18.4 on x86_64-windows
Tables: 35
```

### B. Cloud API Pytest Output
```powershell
# Command:
cd api; .\.venv\Scripts\python -m pytest -v
# Output:
tests/test_bridge_router.py::test_bridge_heartbeat_unauthorized PASSED   [  8%]
tests/test_bridge_router.py::test_bridge_heartbeat_authorized PASSED     [ 16%]
tests/test_bridge_router.py::test_bridge_report_companies PASSED         [ 25%]
tests/test_bridge_router.py::test_bridge_poll_pending_jobs PASSED        [ 33%]
tests/test_bridge_router.py::test_bridge_record_attempt_and_verification PASSED [ 41%]
tests/test_companies_router.py::test_company_lifecycle_and_tally_mapping PASSED [ 50%]
tests/test_domain_models.py::test_uuid7_generation PASSED                [ 58%]
tests/test_domain_models.py::test_tenant_company_tally_hierarchy PASSED  [ 66%]
tests/test_domain_models.py::test_accounting_proposal_multi_step_approval_and_transaction PASSED [ 75%]
tests/test_domain_models.py::test_posting_and_verification_evidence_model PASSED [ 83%]
tests/test_domain_models.py::test_soft_delete_and_audit_event PASSED     [ 91%]
tests/test_main.py::test_read_root PASSED                                [100%]
======================== 12 passed, 1 warning in 1.06s ========================
```

### C. Bridge Pytest Output
```powershell
# Command:
cd bridge; .\.venv\Scripts\python -m pytest -v
# Output:
tests/test_local_store.py::test_enqueue_and_get_pending_jobs PASSED      [  6%]
tests/test_local_store.py::test_update_job_status_and_retry PASSED       [ 12%]
tests/test_local_store.py::test_idempotency_posting_history PASSED       [ 18%]
tests/test_local_store.py::test_tally_health_cache PASSED                [ 25%]
tests/test_main.py::test_main PASSED                                     [ 31%]
tests/test_reconciler.py::test_reconciler_post_and_verify_success PASSED [ 37%]
tests/test_reconciler.py::test_reconciler_prevents_duplicate_on_existing_tally_voucher PASSED [ 43%]
tests/test_reconciler.py::test_reconciler_reconciles_after_network_timeout PASSED [ 50%]
tests/test_tally_adapters.py::test_xml_adapter_get_status_online PASSED  [ 56%]
tests/test_tally_adapters.py::test_xml_adapter_get_companies PASSED      [ 62%]
tests/test_tally_adapters.py::test_xml_adapter_get_ledgers PASSED        [ 68%]
tests/test_tally_adapters.py::test_xml_adapter_create_voucher_success PASSED [ 75%]
tests/test_tally_adapters.py::test_xml_adapter_verify_transaction PASSED [ 81%]
tests/test_tally_adapters.py::test_json_adapter_get_companies PASSED     [ 87%]
tests/test_tally_adapters.py::test_json_adapter_create_voucher PASSED    [ 93%]
tests/test_tally_adapters.py::test_adapter_factory_fallback PASSED       [100%]
============================= 16 passed in 0.39s ==============================
```

### D. Next.js Web Lint & Production Build Output
```powershell
# Command:
cd web; npm run lint ; npm run build
# Output:
> web@0.1.0 lint
> eslint

> web@0.1.0 build
> next build

▲ Next.js 16.3.5 (Turbopack)
✓ Running next.config.ts took 93ms
  Creating an optimized production build ...
✓ Compiled successfully in 538ms
  Running TypeScript ...
  Finished TypeScript in 1377ms ...
  Collecting page data using 5 workers ...
  Generating static pages using 5 workers (4/4) in 444ms
  Finalizing page optimization ...

Route (app)
┌ ○ /
└ ○ /_not-found
○  (Static)  prerendered as static content
```
