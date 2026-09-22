# WAAST360 Golden Path

## Overview
The Golden Path represents the primary, happy-path workflow for processing an invoice in WAAST360 Lite.

## Step-by-Step Flow

1. **Tally connection:** WAAST360 Bridge establishes a secure local connection to the Tally instance.
2. **Company discovery:** The Bridge queries available Tally Companies and registers them in WAAST360.
3. **Invoice upload:** A user uploads an invoice document via the WAAST360 interface.
4. **AI extraction:** An abstracted AI Provider processes the document.
5. **Accounting proposal:** WAAST360 structures the AI output into a standard accounting proposal.
6. **Validation:** Deterministic rules run against the proposal.
7. **Duplicate detection:** The system queries Tally and local DB to prevent double posting.
8. **Human approval:** The user reviews and explicitly approves the entry.
9. **Tally posting:** The Bridge receives the approved entry and pushes it to Tally via the TallyAdapter.
10. **Read-back verification:** The system verifies the posting was successful by querying the new ID/Voucher.
11. **Audit trail:** An immutable record of this entire transaction is finalized.
