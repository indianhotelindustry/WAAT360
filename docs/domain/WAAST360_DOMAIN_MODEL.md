# WAAST360 Domain Model

## Core Entities
The platform must anticipate the following domain hierarchy from day one:

- **Organization**: The top-level tenant.
- **Company**: A logical entity under an organization.
- **Branch**: Physical/logical subset of a Company.
- **Tally Company**: The mapped entity within the Tally Instance.
- **Tally Instance**: The local Tally environment running on the user's machine.
- **Bridge**: The trusted client linked to an Organization/Company.
- **Connection**: The real-time WebSocket or polling connection from the Bridge.
- **Document**: The raw uploaded file (e.g., an Invoice PDF).
- **Document Version**: Iterations of the document.
- **Extraction**: The raw JSON output from the AIProvider.
- **Party / Ledger / Item / Tax**: Master data entities synced from Tally.
- **Transaction / Transaction Line**: The accounting data structure.
- **Accounting Proposal**: The finalized structure ready for validation.
- **Validation**: Rules engine result on a Proposal.
- **Approval**: User sign-off record.
- **Posting Job / Posting Attempt**: Asynchronous queue tasks for Tally.
- **Tally Response**: The JSON/XML result from Tally Adapter.
- **Verification**: The post-posting query to ensure persistence.
- **Exception**: Any failure state.
- **Audit Event**: Immutable logs of all the above.
- **Sync Job / Sync Run**: Background jobs to sync master data.
