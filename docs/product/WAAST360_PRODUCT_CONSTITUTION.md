# WAAST360 Product Constitution

## The Core Product Principle
1. **AI proposes:** AI models extract and suggest accounting entries.
2. **Rules validate:** Deterministic rules check proposals against accounting logic.
3. **Human approves:** The user reviews and authorizes the validated proposals.
4. **Bridge posts:** A trusted local agent relays the approved data.
5. **Tally records:** Tally, as the system of record, processes and records the entry.
6. **WAAST360 verifies:** WAAST360 reads back from Tally to confirm success.
7. **Audit proves:** An immutable audit trail proves the exact sequence of events.

## System Authority
- **Tally:** The ultimate accounting system of record.
- **WAAST360:** The intelligent control/orchestration layer.
- **Bridge:** A trusted local transport and execution component.
- **AI:** Never the final authority.

## Restrictions
- Do not build a Munshi clone.
- Do not copy proprietary Munshi implementation.
- Do not execute or modify the supplied Munshi Tally Connector binary.
