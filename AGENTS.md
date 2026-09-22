# AGENTS.md — WAAST360 Multi-Agent Engineering Guide

This document is the agent-neutral operational manual for engineers and AI agents (Claude Code, Gemini, Antigravity, Codex, etc.) working on **WAAST360** (Wise Accounting Automation System for Tally).

---

## 1. Repository Structure

```
WAAST360/
├── CLAUDE.md              # Claude Code project entry point & rules
├── AGENTS.md              # Agent-neutral engineering guide (this file)
├── .gitignore             # Git exclusions (ignores .env, .venv, node_modules, etc.)
│
├── api/                   # FastAPI Backend (Python 3.14+)
│   ├── alembic/           # Alembic database migrations
│   │   └── versions/      # 390eab233bf5_initial_schema.py (Migration Head)
│   ├── alembic.ini        # Alembic configuration
│   ├── pyproject.toml     # Python package & ruff/pytest configuration
│   ├── requirements.txt   # FastAPI, SQLAlchemy, Alembic, psycopg, etc.
│   ├── .env.example       # Database & environment variable templates
│   ├── src/
│   │   ├── main.py        # FastAPI entrypoint, router mounting, CORS
│   │   ├── core/          # Settings (config.py), Database engine & session (database.py)
│   │   ├── models/        # 34 SQLAlchemy domain entities (entities.py, base.py)
│   │   └── routers/       # Bridge router (bridge.py), Companies router (companies.py)
│   └── tests/             # API test suite (12 tests passing)
│
├── bridge/                # Windows Bridge Client (Python 3.14+)
│   ├── pyproject.toml     # Bridge packaging & ruff/pytest config
│   ├── requirements.txt   # Requests, pydantic, pydantic-settings, etc.
│   ├── src/
│   │   ├── main.py        # Bridge CLI daemon & testing commands
│   │   ├── config.py      # Bridge settings & local configuration
│   │   ├── daemon.py      # Polling heartbeat, discovery & job loop
│   │   ├── adapters/      # TallyAdapter base, JSON, XML, and Factory
│   │   ├── engine/        # PostingReconciler & idempotency engine
│   │   ├── models/        # TallyCapabilities, Domain DTOs
│   │   ├── store/         # BridgeLocalStore (SQLite durable offline queue)
│   │   └── transport/     # BridgeTransport (PollingTransport & PersistentTransport)
│   └── tests/             # Bridge test suite (16 tests passing)
│
├── docs/                  # Architectural, Domain & AI Continuity Documentation
│   ├── architecture/      # WAAST360_ARCHITECTURE.md
│   ├── domain/            # WAAST360_DOMAIN_MODEL.md, ER_RELATIONSHIP_MAP.md
│   ├── product/           # PRODUCT_CONSTITUTION.md, LITE_SCOPE.md, GOLDEN_PATH.md
│   ├── security/          # WAAST360_SECURITY_MODEL.md
│   ├── tally/             # WAAST360_TALLY_INTEGRATION.md
│   ├── testing/           # LIVE_TALLY_CERTIFICATION_GATE.md, README.md
│   └── AI/                # AI Continuity & Repository Knowledge Layer (13 files)
│
└── web/                   # Next.js 16 Frontend (App Router, TypeScript, Tailwind CSS v4)
    ├── package.json       # Dependencies (Next 16, React 19, Tailwind 4)
    ├── tsconfig.json      # TypeScript compiler configuration
    └── src/app/           # Next.js App Router (page.tsx, layout.tsx, globals.css)
```

---

## 2. Core Development Commands

All commands are run from repository root or their specific subfolder on Windows PowerShell:

### A. FastAPI Backend (`api/`)
```powershell
cd api

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run tests
.\.venv\Scripts\python -m pytest -v

# Run linter & formatter
.\.venv\Scripts\ruff check src/ tests/
.\.venv\Scripts\ruff format src/ tests/

# Run database migrations
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\alembic current

# Run local development server
.\.venv\Scripts\uvicorn src.main:app --reload --port 8000
```

### B. Windows Bridge Client (`bridge/`)
```powershell
cd bridge

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run tests
.\.venv\Scripts\python -m pytest -v

# Run linter & formatter
.\.venv\Scripts\ruff check src/ tests/
.\.venv\Scripts\ruff format src/ tests/

# Test local TallyPrime connection (port 9000)
.\.venv\Scripts\python src/main.py test-tally

# Query Tally and synchronize discovered companies to Cloud
.\.venv\Scripts\python src/main.py discover

# Start Bridge daemon polling loop
.\.venv\Scripts\python src/main.py start
```

### C. Next.js Frontend (`web/`)
```powershell
cd web

# Lint code
npm run lint

# Build production bundle (TypeScript & Turbopack verification)
npm run build

# Run local development server
npm run dev
# Dashboard opens on http://localhost:3000
```

---

## 3. Database & Migration Workflow

- **PostgreSQL**: Local PostgreSQL 18.x running on port 5432, database `waast360`.
- **Environment Contract**: `DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/waast360`.
- **Primary Keys**: UUIDv7 (via Python 3.14's native `uuid.uuid7()`).
- **Entity Definitions**: All 34 domain entities are located in [`api/src/models/entities.py`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/api/src/models/entities.py).
- **Migration Head**: `390eab233bf5_initial_schema.py` defines all 35 tables (including `alembic_version`).
- **Rules**:
  1. Never delete migrations or modify applied migrations without an explicit forward migration.
  2. Keep `JSONVariant = JSON().with_variant(JSONB, "postgresql")` to support PostgreSQL JSONB and SQLite unit tests.

---

## 4. Bridge & Tally Integration Architecture

- **Topology**: Outbound-only from Bridge to Cloud:
  $$\text{TallyPrime (localhost:9000)} \xleftarrow{\text{Local HTTP}} \text{WAAST360 Bridge} \xrightarrow[\text{HTTPS Polling}]{\text{Outbound}} \text{WAAST360 Cloud}$$
- **Security**: Port 9000 is loopback/internal only. Cloud never opens a socket to port 9000.
- **Explicit Company Binding**: All adapter calls pass `svCurrentCompany` context explicitly to prevent Tally falling back to the UI's active on-screen company.
- **Tally Location Reality**: TallyPrime is installed on the client's office machine. Local development laptops do not run Tally; `localhost:9000` connection refusal is an expected environment state.
- **Certification Gate**: `LIVE-TALLY-CERT-001` must be satisfied on the client office machine prior to production sign-off.

---

## 5. Security & Secret Hygiene

1. `.env` and `*.env` files are ignored by git.
2. `api/.env.example` contains placeholders only (`your_local_password`).
3. NEVER commit passwords, API keys, private keys, or tokens.
4. Soft deletion is required for all financial records (`is_deleted`, `deleted_at`, `deleted_by`, `deletion_reason`).
5. Every financial write requires an immutable `AuditEvent` entry.

---

## 6. AI Continuity & Handoff Protocol

When ending a session or handing off work to another AI agent:
1. Verify code works by running the test suites (`api`, `bridge`, `web`).
2. Update [`docs/AI/CURRENT_STATE.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/CURRENT_STATE.md).
3. Update [`docs/AI/ACTIVE_WORK.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/ACTIVE_WORK.md).
4. Update [`docs/AI/NEXT_ACTIONS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/NEXT_ACTIONS.md).
5. Update [`docs/AI/VERIFICATION_STATUS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/VERIFICATION_STATUS.md).
6. Append a session summary to [`docs/AI/SESSION_LOG.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/SESSION_LOG.md).
7. If any architectural decisions were made, document them in [`docs/AI/DECISIONS.md`](file:///c:/Users/SIPL%20Server/Downloads/DSS/WAAST360/docs/AI/DECISIONS.md).
