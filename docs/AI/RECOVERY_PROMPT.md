# RECOVERY PROMPT FOR INCOMING AI AGENT

Copy and paste the prompt below into any new AI session (Claude Code, Gemini, Antigravity, or Codex) to resume work seamlessly with zero conversational history:

---

```markdown
You are taking over the existing WAAST360 (Wise Accounting Automation System for Tally) repository.

You have no access to previous conversation history or model memory.
You must recover project context entirely from the repository ground truth.

IMMEDIATE FIRST ACTIONS:
1. Read the authoritative orientation files in this order:
   - CLAUDE.md (or AGENTS.md)
   - docs/AI/CURRENT_STATE.md
   - docs/AI/ACTIVE_WORK.md
   - docs/AI/NEXT_ACTIONS.md
   - docs/AI/DECISIONS.md
   - docs/AI/KNOWN_ISSUES.md
   - docs/AI/VERIFICATION_STATUS.md
   - docs/AI/ARCHITECTURE_CONTEXT.md
   - docs/AI/PRODUCT_CONTEXT.md
   - docs/AI/ENVIRONMENT.md

2. Inspect git status and verify current repository state:
   - Run `git status`
   - Run API test suite: `cd api && .\.venv\Scripts\python -m pytest -q`
   - Run Bridge test suite: `cd bridge && .\.venv\Scripts\python -m pytest -q`
   - Run Web build: `cd web && npm run build`

CRITICAL FACTS & CONSTRAINTS:
- Product: WAAST360 Lite on a Prime-grade foundation.
- Core Accounting Principle:
  AI proposes → Rules validate → Human approves → Bridge posts → Tally records → WAAST360 verifies → Audit proves.
- Entity Separation: WAAST360 Company ≠ Tally Instance ≠ Tally Company ≠ Bridge.
- Tally Location Reality: The development laptop does NOT have TallyPrime installed. TallyPrime is on the client's office machine. Connection failure on localhost:9000 is an expected environment state, not a blocker.
- Certification Gate: LIVE-TALLY-CERT-001 is PENDING client office machine deployment. Local development utilizes simulated adapter mode.
- System of Record: Tally is the accounting system of record. WAAST360 is the control and orchestration layer.
- Never commit secrets or expose passwords.

YOUR MISSION:
- Pick the top unblocked task from `docs/AI/NEXT_ACTIONS.md`.
- Implement clean, verified code conforming to existing architecture.
- Run tests and linters.
- Update `docs/AI/CURRENT_STATE.md`, `docs/AI/ACTIVE_WORK.md`, `docs/AI/NEXT_ACTIONS.md`, `docs/AI/VERIFICATION_STATUS.md`, and `docs/AI/SESSION_LOG.md` before concluding.
```
