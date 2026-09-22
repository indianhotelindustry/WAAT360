# ENVIRONMENT & SETUP GUIDE — WAAST360

This guide details how to reproduce the WAAST360 development and test environment.

---

## 1. Verified Software Versions (Ground Truth)

- **Operating System**: Microsoft Windows 11 (PowerShell terminal)
- **Python**: `3.14.5` (native `uuid.uuid7()` support)
- **Node.js**: `v20.20.2`
- **npm**: `10.8.2`
- **PostgreSQL**: `PostgreSQL 18.4 on x86_64-windows`
- **Database Engine**: `postgresql+psycopg`

---

## 2. Port Allocation

| Port | Service | Host Binding | Notes |
| :--- | :--- | :--- | :--- |
| **5432** | PostgreSQL 18.x | `127.0.0.1` | Local database server (database: `waast360`) |
| **8000** | FastAPI Cloud API | `127.0.0.1` | REST endpoints, CORS enabled |
| **3000** | Next.js 16 Web Dashboard | `127.0.0.1` | Frontend UI |
| **9000** | TallyPrime HTTP/ODBC Server | `127.0.0.1` | Target Tally runtime (client office machine) |

---

## 3. Secret & Credential Management

> [!CAUTION]
> **NO SECRETS IN CODE OR DOCUMENTATION**:
> - Never store real passwords, API keys, or tokens in git-tracked files.
> - `.env` files are strictly excluded via `.gitignore`.
> - Always use placeholders in documentation: `<LOCAL_DB_PASSWORD>`, `<GEMINI_API_KEY>`, `<BRIDGE_KEY>`.

---

## 4. Virtual Environments & Setup

### A. FastAPI Backend (`api/`)
```powershell
cd api

# Virtual environment path: api/.venv
# If creating from scratch:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure environment variables
# Copy .env.example to .env and insert your local password:
# DATABASE_URL=postgresql+psycopg://postgres:<LOCAL_DB_PASSWORD>@localhost:5432/waast360

# Apply migrations
.\.venv\Scripts\alembic upgrade head

# Run server
.\.venv\Scripts\uvicorn src.main:app --reload --port 8000
```

### B. Bridge Integration Agent (`bridge/`)
```powershell
cd bridge

# Virtual environment path: bridge/.venv
# If creating from scratch:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run connectivity test against Tally
.\.venv\Scripts\python src/main.py test-tally

# Query companies and sync to Cloud
.\.venv\Scripts\python src/main.py discover

# Run polling daemon
.\.venv\Scripts\python src/main.py start
```

### C. Next.js Web Frontend (`web/`)
```powershell
cd web

# Install dependencies (Node 20+)
npm install

# Run development server
npm run dev

# Run linting
npm run lint

# Build production bundle
npm run build
```

---

## 5. Verification Command Cheatsheet

```powershell
# Run API tests (12 tests)
cd api; .\.venv\Scripts\python -m pytest -v

# Run Bridge tests (16 tests)
cd bridge; .\.venv\Scripts\python -m pytest -v

# Run Python linter & formatters
cd api; .\.venv\Scripts\ruff check src/ tests/
cd bridge; .\.venv\Scripts\ruff check src/ tests/

# Run Frontend quality checks
cd web; npm run lint ; npm run build
```
