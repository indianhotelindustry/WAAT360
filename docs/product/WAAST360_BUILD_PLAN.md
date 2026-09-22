# WAAST360 Build Plan

## Phase 1: Foundation (Current)
- Initialize project structure.
- Document Product Constitution, Domain Model, Architecture.
- Define interface boundaries (`AIProvider`, `TallyAdapter`).

## Phase 2: Lite Vertical Slice (Days 1-3)
- Scaffold a simple Node.js/Python API and a modern web UI (e.g., React/Next.js/Vite).
- Implement a basic local Bridge script.
- Hardcode master data if Tally sync is not yet stable, to unblock UI.
- Implement the AI extraction using `GeminiProvider`.

## Phase 3: The Golden Path (Days 3-5)
- Wire up the full flow from File Upload -> AI -> Proposal -> Approval.
- Connect Bridge to Tally HTTP port.
- Push the approved voucher to Tally.
- Verify read-back.

## Phase 4: Prime Refinement (Future)
- Advanced syncing (Delta syncs).
- Comprehensive UI for exception handling.
- Complex GST handling.
