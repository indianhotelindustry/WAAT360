# KNOWN ISSUES & ENVIRONMENT CONSTRAINTS — WAAST360

This document tracks verified blockers, environmental limitations, pending certifications, and technical debt.

---

## A. Confirmed Blockers
- **None at present**.
- *Historical Note*: The previous PostgreSQL password/migration blocker has been **RESOLVED**. PostgreSQL 18.x is authenticated, migrations are applied to head `390eab233bf5`, and 35 tables are active.

---

## B. Environment Limitations
1. **No Local TallyPrime on Development Machine**:
   - **Fact**: TallyPrime is not installed on this development laptop.
   - **Fact**: Live TallyPrime is located on the **client's office machine**.
   - **Impact**: Testing against `127.0.0.1:9000` on the development laptop returns `[WinError 10061] No connection could be made because the target machine actively refused it`.
   - **Resolution**: This is an **expected environment state**, NOT a code defect. Development and testing use the `TallyAdapter` contract and simulated adapter mode.

2. **Windows Path Separators**:
   - Commands in documentation and test runners must respect PowerShell syntax (`\` paths, `;` separator instead of `&&`).

---

## C. Pending Live Certification Gates
1. **`LIVE-TALLY-CERT-001`**:
   - **Target**: Client's office machine running TallyPrime on port 9000.
   - **Status**: **PENDING**.
   - **Specification**: [`docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md).
   - **Requirement**: Must be executed and signed off prior to client production release.

---

## D. Technical Debt
1. **PersistentTransport Stub**:
   - In `bridge/src/transport/persistent.py`, the WebSocket/gRPC persistent transport is currently an architectural placeholder. PollingTransport handles all Lite communication.
2. **In-Memory Cache in Bridge Router**:
   - `api/src/routers/bridge.py` maintains in-memory dictionaries `_bridge_states` alongside PostgreSQL persistence for rapid response in dev. Long-term, multi-instance Cloud deployments will use Redis for transient bridge state.

---

## E. Documentation Drift
- **None identified during the current audit**. Code, database migrations, and documentation are strictly aligned.

---

## F. Future Operational Risks
1. **Large Tally Company Master Retrieval**:
   - Retrieving tens of thousands of ledgers over HTTP port 9000 without pagination can cause Tally memory spikes. Lite addresses this by scoping queries to active companies; pagination should be prioritized in Prime.
2. **Tally Modal Dialog Blocks**:
   - If a user opens an interactive modal dialog inside TallyPrime on the host machine, Tally may delay HTTP responses until the modal is closed. Handled in Bridge via configurable timeouts and retry reconciler.
