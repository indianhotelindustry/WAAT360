# CLAUDE.md — WAAST360 Project Instructions

---------------------------------------------------------------
WAAST360
Wise Accounting Automation System for Tally
---------------------------------------------------------------

## Product Overview
- **Product**: WAAST360
- **Expansion**: Wise Accounting Automation System for Tally
- **Product Family**: WAAST360 Lite (Current Focus) / WAAST360 Prime (Future Vision)
- **Strategy**: Perfect Planning → Strong Foundation → WAAST360 Lite → WAAST360 Prime

## Core Accounting Philosophy
```
AI proposes
  → Rules validate
  → Human approves
  → Bridge posts
  → Tally records
  → WAAST360 verifies
  → Audit proves
```

## Systems and Boundaries
- **System of Record**: Tally is the accounting system of record.
- **Orchestration Layer**: WAAST360 is the intelligent control and orchestration layer.
- **Bridge Agent**: WAAST360 Bridge is the trusted local execution and transport layer between WAAST360 Cloud and TallyPrime.

## Critical Entity Separation
The domain model strictly separates entities. Never collapse or conflate them:
```
Organization
  └── Company (WAAST360 internal accounting entity)
        └── Branch
Tally Instance (Runtime host/port, e.g. 127.0.0.1:9000)
  └── Tally Company (Native Tally identity, GUID, FY, Books From)
Bridge (Local Windows execution agent)
  └── Connection
Accounting Workspace
Sync Profile
```
**Strict Isolation Rule**:
$$\text{WAAST360 Company} \ne \text{Tally Company} \ne \text{Tally Instance} \ne \text{Bridge}$$

## Architecture Rules
1. **Never Bypass Bridge**: Never bypass the Bridge for normal Tally operations.
2. **Never Expose Port 9000**: Do not expose Tally port 9000 publicly. Bridge initiates all communication outbound to WAAST360 Cloud.
3. **Outbound-Initiated Secure Channel**: Bridge uses HTTPS polling in Lite (with persistent transport stubs for Prime).
4. **Capability-Based Adapter**: Tally adapter (`TallyAdapter`) is capability-based:
   - JSON-first where supported (TallyPrime 7.0+).
   - XML envelope fallback retained for compatibility.
   - TDL is not mandatory for Lite.
5. **Prime-Grade Foundation**: Lite capabilities run on a Prime-grade architectural foundation. Do not create throwaway Lite code.
6. **Proposed vs Authoritative Accounting**: AI output is proposed accounting, never authoritative accounting.
7. **Human Approval Gate**: Human approval is strictly required before financial posting unless an explicitly authorized future workflow specifies otherwise.
8. **No Destructive Deletion**: Financial records are never destructively deleted; soft-deletion with audit tracking only.
9. **Accounting Reversals**: Reversals and adjustments must use standard accounting mechanisms.
10. **Deterministic Idempotency**: Idempotency is implemented via client-generated correlation IDs, pre-check and post-check reconciliation, not as an unverified assumption.
11. **Live vs Simulated Testing**: Live Tally testing must always be distinguished from simulated adapter testing. Never claim live certification without verifiable evidence from a running TallyPrime instance.
12. **Locked Decisions**: Do not casually alter locked architectural decisions without an ADR.

---

## Operating Instructions for AI Agents

### Before Coding:
Read the following authoritative documents in order:
1. [`docs/AI/CURRENT_STATE.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/CURRENT_STATE.md)
2. [`docs/AI/ACTIVE_WORK.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/ACTIVE_WORK.md)
3. [`docs/AI/NEXT_ACTIONS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/NEXT_ACTIONS.md)
4. [`docs/AI/DECISIONS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/DECISIONS.md)
5. [`docs/AI/VERIFICATION_STATUS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/VERIFICATION_STATUS.md)
6. [`docs/AI/KNOWN_ISSUES.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/KNOWN_ISSUES.md)
7. [`docs/AI/ENVIRONMENT.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/ENVIRONMENT.md)

### After Meaningful Work:
Update the relevant AI continuity documents:
- Update `docs/AI/CURRENT_STATE.md` with new factual progress.
- Update `docs/AI/ACTIVE_WORK.md` and `docs/AI/NEXT_ACTIONS.md`.
- Update `docs/AI/VERIFICATION_STATUS.md` with exact command outputs.
- Add an entry to `docs/AI/SESSION_LOG.md`.

### Strict Prohibitions:
- NEVER fabricate implementation status.
- NEVER claim live Tally certification without live Tally evidence.
- NEVER rewrite architecture merely for convenience.
- NEVER remove existing functionality without understanding dependencies.
- NEVER commit secrets or hard-code credentials.
- NEVER treat simulated tests as live Tally tests.
- NEVER overwrite locked product decisions without documenting an ADR.

**When uncertain**: Inspect first. Then decide. Do not guess.
