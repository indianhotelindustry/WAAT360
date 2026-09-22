# LIVE-TALLY-CERT-001: Deployment-Time Live TallyPrime Certification Gate

## 1. Overview
- **Gate Identifier**: `LIVE-TALLY-CERT-001`
- **Purpose**: Ensure formal verification against a genuine, running TallyPrime instance before production or client demonstration sign-off.
- **Context**: The development laptop does not host TallyPrime. Live TallyPrime is hosted on the client's office machine. Local development utilizes `TallySimulatedAdapter` for deterministic development and testing, while live certification is gated by this specification.

---

## 2. Pre-Flight Configuration on Client Machine

Before executing this certification gate, ensure the client's office machine meets the following criteria:

1. **TallyPrime Running**: TallyPrime is opened and at least one target company (with accounting books and master ledgers) is actively loaded.
2. **HTTP/ODBC Server Enabled**:
   - In TallyPrime, press **F12 (Configure)** $\rightarrow$ **Advanced Configuration**.
   - Set **Tally is acting as**: `Both` (or `Server`).
   - Set **Enable ODBC**: `Yes`.
   - Set **Port**: `9000` (or configured port).
   - Accept the changes and restart TallyPrime if prompted.
3. **Firewall & Loopback**: Ensure loopback connections on `127.0.0.1:9000` are permitted for the local Bridge process.

---

## 3. Four-Step Certification Protocol

### Step 1: Connectivity & Capabilities Probe
Execute the Bridge test-tally command:
```powershell
cd bridge
.\.venv\Scripts\python src/main.py test-tally --host 127.0.0.1 --port 9000
```
**Pass Criteria**:
- `Online`: `True`
- `Version`: Detected valid Tally version (e.g. `TallyPrime 7.0` or `TallyPrime 4.x`)
- `Response Time`: `< 500 ms`
- `Capabilities`: XML read/write verified (and JSON if 7.0+).

### Step 2: Live Company Discovery & Cloud Sync
Execute the discovery command:
```powershell
.\.venv\Scripts\python src/main.py discover --host 127.0.0.1 --port 9000
```
**Pass Criteria**:
- List of companies currently loaded in Tally is returned.
- Discovered companies contain native `tally_guid`, `company_name`, `financial_year_from`, and `books_from`.
- Cloud API reports: `status: synchronized`, and records are upserted into PostgreSQL `tally_companies`.

### Step 3: Company Association in WAAST360
Open the WAAST360 Dashboard (`http://localhost:3000`):
**Pass Criteria**:
- Discovered Tally company appears in the "Discovered Tally Companies" pane with status `DISCOVERED`.
- User executes **1-Click Quick Map** or links to an existing WAAST360 Company.
- Status immediately updates to `MAPPED`.

### Step 4: Real Voucher Posting & Read-Back Verification
Post a test voucher (Purchase or Journal) via the Bridge daemon:
```powershell
.\.venv\Scripts\python src/main.py start
```
**Pass Criteria**:
- Voucher is created in TallyPrime (`TallyAdapter.create_voucher()` returns `success=True` and a valid Tally `voucher_number`).
- Read-back verification (`TallyAdapter.verify_transaction()`) returns `is_verified=True` and `status="VERIFIED"`.
- `VerificationResult` evidence is recorded in PostgreSQL.
- Voucher is visible inside TallyPrime's Day Book / Voucher Register.

---

## 4. Sign-Off Record

| Item | Requirement | Status | Evidence / Notes |
| :--- | :--- | :--- | :--- |
| **Connectivity** | Tally responds on port 9000 | PENDING | Client office machine deployment required |
| **Discovery** | Live company list parsed | PENDING | Client office machine deployment required |
| **Mapping** | Bound to WAAST360 company | PENDING | Client office machine deployment required |
| **Posting** | Test voucher posted in Tally | PENDING | Client office machine deployment required |
| **Verification**| Read-back verification proved | PENDING | Client office machine deployment required |
| **Sign-Off Date**| Timestamp of live certification | PENDING | Not certified on dev laptop |
| **Engineer** | Certifying engineer / agent | PENDING | Pending client machine access |
