# WAAST360 — AI Continuity & Handoff Hub

Welcome, incoming AI agent.

This directory (`docs/AI/`) is the **authoritative continuity layer** of the WAAST360 codebase. It was constructed so you can take over this project immediately with zero loss of context, without needing access to prior chat transcripts or model memory.

---

## 1. Quick Orientation Map

| Document | Purpose | Read Priority |
| :--- | :--- | :---: |
| [`RECOVERY_PROMPT.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/RECOVERY_PROMPT.md) | Ready-to-paste prompt to initialize any AI session | **Immediate** |
| [`CURRENT_STATE.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/CURRENT_STATE.md) | Verified factual status of the codebase right now | **1** |
| [`ACTIVE_WORK.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/ACTIVE_WORK.md) | What is currently in progress | **2** |
| [`NEXT_ACTIONS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/NEXT_ACTIONS.md) | Prioritized backlog of exact next tasks | **3** |
| [`DECISIONS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/DECISIONS.md) | Locked architectural decision records (DEC-001 to DEC-018) | **4** |
| [`KNOWN_ISSUES.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/KNOWN_ISSUES.md) | Active environment facts & limitations (no fake blockers) | **5** |
| [`VERIFICATION_STATUS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/VERIFICATION_STATUS.md) | Test suites, lint status, and verification evidence | **6** |
| [`ARCHITECTURE_CONTEXT.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/ARCHITECTURE_CONTEXT.md) | Detailed diagrams, topologies, and file mappings | **7** |
| [`PRODUCT_CONTEXT.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/PRODUCT_CONTEXT.md) | Product DNA, Lite scope, and deferred Prime vision | **8** |
| [`ENVIRONMENT.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/ENVIRONMENT.md) | Reproduction guide: versions, ports, and dev commands | **9** |
| [`SESSION_LOG.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/SESSION_LOG.md) | Chronological session audit trail | **10** |
| [`DOCUMENTATION_DRIFT.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/DOCUMENTATION_DRIFT.md) | Discrepancies between docs and active code | **11** |

---

## 2. Source-of-Truth Hierarchy

When evaluating the system or resolving conflicting statements, always adhere to this priority:

1. **Actual Code and Database Migrations** (Ground Truth)
2. **Automated Test Results and Verification Evidence**
3. **Locked Architecture & Product Documents** (`docs/` and `docs/AI/DECISIONS.md`)
4. **AI Continuity Documents** (`docs/AI/`)
5. **README & Peripheral Notes**
6. **Previous Chat Context / Conversational Memory** (Lowest Priority)

If code contradicts documentation, document it as a `DOCUMENTATION_DRIFT` and reconcile it factually. Never guess.

---

## 3. Five Critical Truths You Must Know

1. **Product**: **WAAST360** (Wise Accounting Automation System for Tally) — building **WAAST360 Lite** on a **Prime-grade foundation**.
2. **Core Accounting Principle**:
   $$\text{AI proposes} \rightarrow \text{Rules validate} \rightarrow \text{Human approves} \rightarrow \text{Bridge posts} \rightarrow \text{Tally records} \rightarrow \text{WAAST360 verifies} \rightarrow \text{Audit proves}$$
3. **Entity Separation**: $\text{WAAST360 Company} \ne \text{Tally Instance} \ne \text{Tally Company} \ne \text{Bridge}$.
4. **Tally Location Reality**: TallyPrime is installed on the **client's office machine**, NOT this development laptop. The connection refusal on `127.0.0.1:9000` is an expected environment state, not a defect. Live certification is gated by [`docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md).
5. **Current State**: Phase 2A (Scaffolding), Phase 2B (Database & Domain), Phase 2C (Bridge Subsystem), and Phase 2D (Company Discovery & Mapping) are 100% complete and tested. Next is Phase 2E/Golden Path (Document Upload $\rightarrow$ Gemini Extraction $\rightarrow$ Accounting Proposal $\rightarrow$ Validation $\rightarrow$ Approval $\rightarrow$ Posting $\rightarrow$ Read-back Verification $\rightarrow$ Audit Proof).
