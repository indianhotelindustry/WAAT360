# WAAST360 Tally Integration

## Core Tenets
1. **Tally is the Source of Truth:** Master data (ledgers, items, taxes) must be synced from Tally. WAAST360 does not invent master data.
2. **Adapter Pattern:** Tally communication is strictly via the `TallyAdapter`.
3. **Bridge Local Execution:** WAAST360 Cloud cannot talk directly to Tally. It must dispatch a `Posting Job` to the Bridge.

## The Tally Connector (Forensic Reference)
- A pre-existing Munshi Tally Connector binary is supplied for reference.
- **DO NOT EXECUTE OR MODIFY IT.** It is strictly for forensic review to understand Tally API quirks (like specific XML tagging).
- A new, clean TallyAdapter logic will be written to interface with Tally's HTTP port (usually 9000).

## Golden Path Tally Interactions
- Connect and authenticate (if required by TDL/Admin).
- `GetCompaniesList`: Fetch active companies.
- `ImportData`: Post the voucher (Purchase/Sales).
- `ExportData`: Read back the voucher by ID/VoucherNumber for Verification.
