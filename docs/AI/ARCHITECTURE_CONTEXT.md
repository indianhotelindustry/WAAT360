# ARCHITECTURE CONTEXT — WAAST360

This document describes the architectural topology, component boundaries, and internal mechanics of WAAST360.

---

## 1. System Topology

```
┌──────────────────────────────────────────────────────────────────┐
│                      WAAST360 CLOUD                             │
│                                                                  │
│   Next.js 16 Web UI              FastAPI Core API                │
│   (App Router, React 19)         (Python 3.14)                   │
│         │                               │                        │
│         └────────── REST API ───────────┤                        │
│                                         │                        │
│                                 PostgreSQL 18.x                  │
│                                 (34 Domain Entities, UUIDv7)     │
└─────────────────────────────────────────┬────────────────────────┘
                                          │
                                          │ Outbound Secure HTTPS / Polling
                                          │ (X-Bridge-Client-Id, X-Bridge-Key)
                                          │
┌─────────────────────────────────────────▼────────────────────────┐
│                   WAAST360 BRIDGE (Windows Client)               │
│                                                                  │
│   PollingTransport ───► PostingReconciler ───► BridgeLocalStore  │
│                               │                 (SQLite Queue)   │
│                               ▼                                  │
│                          TallyAdapter                            │
│                        ┌──────┴──────┐                           │
│                        │             │                           │
│                 TallyJsonAdapter  TallyXmlAdapter                │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                │ Loopback HTTP (127.0.0.1:9000)
                                │ Context: <SVCURRENTCOMPANY>
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                   TALLYPRIME RUNTIME                             │
│                   (System of Record)                             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Entity Isolation & Hierarchy

The domain model prevents conflation between client tenant entities and local Tally runtime instances:

```
[ Organization ]
  │
  ├──o{ [ Company ] (WAAST360 Accounting Entity, PAN, GSTIN)
  │       │
  │       └──o{ [ TallyCompany ] (MAPPED association: 1 Company to 1 TallyCompany)
  │
  └──o{ [ TallyInstance ] (Host/Port Runtime: 127.0.0.1:9000)
          │
          ├──o{ [ TallyCompany ] (Contains: 1 Instance to N Tally Companies)
          │
          └──o{ [ Bridge ] (Connects to: 1 Bridge to 1 Tally Instance)
                  │
                  └──o{ [ Connection ] (Heartbeat & session history)
```

### Critical Rules:
1. `TallyInstance`: Represents the machine/port hosting Tally (`127.0.0.1:9000`).
2. `TallyCompany`: Represents a distinct company loaded inside Tally with native `tally_guid`, `company_name`, `financial_year`, and `books_from`.
3. `Company`: Represents the WAAST360 internal accounting tenant.
4. `Bridge`: Represents the installed background agent on the Windows machine.

---

## 3. Subsystem Breakdown & Repository Paths

### A. Cloud API Backend ([`api/src/`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/api/src/))
- **Entrypoint**: [`api/src/main.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/api/src/main.py) — mounts routers, configures CORS middleware.
- **Database Engine**: [`api/src/core/database.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/api/src/core/database.py) — SQLAlchemy session generator `get_db()`.
- **Domain Entities**: [`api/src/models/entities.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/api/src/models/entities.py) — all 34 domain entities.
- **Bridge Contracts**: [`api/src/routers/bridge.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/api/src/routers/bridge.py) — heartbeat, company reporting, job queue polling, attempt logging, and verification evidence reporting.
- **Company Management**: [`api/src/routers/companies.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/api/src/routers/companies.py) — company creation, TallyCompany listing, manual mapping, and 1-click quick-map.
- **Migrations**: [`api/alembic/versions/390eab233bf5_initial_schema.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/api/alembic/versions/390eab233bf5_initial_schema.py) — Alembic migration head.

### B. Bridge Integration Agent ([`bridge/src/`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/))
- **CLI Runner**: [`bridge/src/main.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/main.py) — commands: `start`, `test-tally`, `discover`, `status`.
- **Daemon Loop**: [`bridge/src/daemon.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/daemon.py) — operational cycle: health check $\rightarrow$ heartbeat $\rightarrow$ company discovery $\rightarrow$ poll jobs $\rightarrow$ drain queue.
- **Tally Adapters**:
  - Base: [`bridge/src/adapters/base.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/adapters/base.py) — abstract capability contract.
  - JSON: [`bridge/src/adapters/json_adapter.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/adapters/json_adapter.py) — native JSON for TallyPrime 7.0+.
  - XML: [`bridge/src/adapters/xml_adapter.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/adapters/xml_adapter.py) — XML envelope generation with `<SVCURRENTCOMPANY>` context injection.
  - Factory: [`bridge/src/adapters/factory.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/adapters/factory.py) — selects adapter by probing capabilities.
- **Local Durable Store**: [`bridge/src/store/local_store.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/store/local_store.py) — SQLite queue, job states, and idempotency ledger.
- **Posting Reconciler**: [`bridge/src/engine/reconciler.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/engine/reconciler.py) — prevents duplicate voucher creation:
  1. Pre-check: queries Tally by reference number to check if already posted.
  2. Execute: creates voucher via adapter.
  3. Post-check: reads back created voucher to verify amounts and capture GUID.
- **Transport**:
  - [`bridge/src/transport/polling.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/transport/polling.py) — outbound HTTPS client.
  - [`bridge/src/transport/persistent.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/bridge/src/transport/persistent.py) — Prime persistent channel stub.

### C. Web Frontend ([`web/src/app/`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/web/src/app/))
- **Dashboard**: [`web/src/app/page.tsx`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/web/src/app/page.tsx) — real-time Bridge and Tally status, company discovery list, WAAST360 company registry, mapping modal, and 1-click quick-map.
- **Styling**: [`web/src/app/globals.css`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/web/src/app/globals.css) — Tailwind CSS v4 design system.

---

## 4. Idempotency & Error Reconciliation

Network timeouts between Bridge and Tally can result in ambiguous outcomes (the voucher might have been recorded in Tally even though the HTTP response timed out).

```
[ Bridge ] ──────────────── Create Voucher ────────────────► [ TallyPrime ]
    │                                                              │
    │ ◄─────────────────── Network Timeout / Disconnect ───────────┘
    │
    ▼
[ Reconciler ]
    │
    ├── Step 1: Query Tally for Reference Number (e.g. BILL-9901)
    │           ├── If Found ──► Reconcile as SUCCESS (Do NOT re-post!)
    │           └── If Not Found ──► Safe to Retry Post
    │
    └── Step 2: Read-Back Verification
                └── Match actual amount, date, and ledgers against proposal
```
This guarantees that retries never cause duplicate financial records inside Tally.
