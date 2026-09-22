# PRODUCT CONTEXT — WAAST360

## 1. Product Identity
- **Product Name**: **WAAST360**
- **Expansion**: Wise Accounting Automation System for Tally
- **Purpose**: Intelligent accounting automation, document extraction, rules validation, and posting orchestration around TallyPrime.
- **Product Tiers**:
  1. **WAAST360 Lite**: Focused, commercially usable initial vertical slice (immediate 3–5 day delivery context).
  2. **WAAST360 Prime**: Enterprise-grade multi-tenant automation, multi-entity consolidation, and advanced AI platform.

---

## 2. Core Accounting Constitution
WAAST360 enforces an inviolable seven-step accounting lifecycle:

```
1. AI PROPOSES
   Extracts invoice line items, tax components, and suggests double-entry ledger allocations.
   
2. RULES VALIDATE
   Deterministic rules verify mathematical balance (Debits == Credits), tax rates, and party mapping.
   
3. HUMAN APPROVES
   A human accountant reviews, modifies if necessary, and explicitly approves the proposal.
   
4. BRIDGE POSTS
   The local Bridge executes the posting to Tally via the capability adapter.
   
5. TALLY RECORDS
   Tally acts as the authoritative system of record and commits the voucher.
   
6. WAAST360 VERIFIES
   Bridge queries Tally to read back the newly created voucher, verifying amounts and capturing the native GUID.
   
7. AUDIT PROVES
   An immutable audit trail records timestamps, human approver, raw AI payload, and Tally verification evidence.
```

---

## 3. WAAST360 Lite Scope vs Deferred Prime Scope

| Capability | WAAST360 Lite (Current Scope) | WAAST360 Prime (Deferred Vision) |
| :--- | :--- | :--- |
| **Voucher Types** | Purchase Vouchers (Invoices / Bills) | Sales, Journals, Payments, Receipts, Contra |
| **Tally Integration** | Standard HTTP/XML & JSON (Port 9000) | Native TDL extensions, ODBC direct query, WebSockets |
| **Bridge Transport** | Outbound HTTPS Polling | Persistent bidirectional channels (gRPC / WebSockets) |
| **Approval Flow** | Single/Dual Step Human Approval | Complex multi-tier hierarchical workflow engine |
| **AI Extraction** | Google Gemini (structured schema) | Multi-model routing (Gemini, Claude, local OCR fallback) |
| **Inventory** | Basic line item extraction | Multi-location godowns, batch/lot tracking, expiry tracking |
| **Multi-Tenancy** | Single Organization, Multi-Company | Multi-Organization enterprise with RBAC hierarchies |
| **Deployment Target** | Local Windows Bridge + Cloud API | Google Cloud Run, Cloud SQL, Multi-region high availability |

> [!WARNING]
> **Scope Discipline**: Do not silently pull Prime features into Lite. Deliver the Lite Golden Path cleanly on the Prime-grade foundation.
