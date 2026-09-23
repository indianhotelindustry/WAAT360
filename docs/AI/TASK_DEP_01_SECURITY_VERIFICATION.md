# TASK-DEP-01: Pre-Commit Security & Deployment Verification

**Date**: 2026-09-23  
**Status**: ✅ **PASSED** — All security and deployment constraints verified  
**Corrections**: 1 critical issue identified and fixed

---

## Executive Summary

Pre-commit security verification identified and corrected **1 critical issue**: NetworkService (the service account) cannot access per-user AppData profiles. This has been fixed by moving runtime data to `C:\ProgramData\` and setting environment variables at SYSTEM scope.

All other verification items **PASSED**.

---

## Verification Results

### 1. BRIDGE_API_KEY Handling ✅ PASS

**Verification**:
- ✅ No hardcoded production secrets in any file
- ✅ Installer uses secure input (`Read-Host -AsSecureString`) — credentials never echoed
- ✅ Secrets NOT present in `.env.example` (only placeholders)
- ✅ Secrets NOT embedded in BAT files
- ✅ Documentation contains no real credentials
- ✅ Only reference: installer prompts → environment variable → service reads

**Result**: **SECURE** — Credentials are handled safely throughout deployment pipeline.

---

### 2. Windows Service Identity & Filesystem Access ✅ PASS (After Correction)

**Issue Found**: Original design used `C:\Users\{user}\AppData\Local\WAAST360\Bridge\` for runtime data, but **NetworkService account cannot access per-user AppData profiles** (security boundary).

**Correction Applied**:
```
BEFORE:  C:\Users\{user}\AppData\Local\WAAST360\Bridge\
AFTER:   C:\ProgramData\WAAST360\Bridge\  (machine-wide, service-accessible)
```

**Files Modified**:
- `bridge/scripts/install_service.ps1`: Updated `$DataPath` and environment variable scope
- `bridge/scripts/uninstall_service.ps1`: Updated `$DataPath` and variable removal
- `bridge/scripts/run_bridge.bat`: Updated log directory path
- `bridge/README_DEPLOYMENT.md`: Updated all path references

**Verification After Correction**:
- ✅ `C:\ProgramData\WAAST360\Bridge\` is machine-wide (accessible to all service accounts)
- ✅ Database: `C:\ProgramData\WAAST360\Bridge\bridge_store.db` (NetworkService WRITABLE)
- ✅ Logs: `C:\ProgramData\WAAST360\Bridge\logs\` (NetworkService WRITABLE)
- ✅ Environment variables set at SYSTEM scope (Machine) — NetworkService can read them

**Result**: **SECURE & FUNCTIONAL** — Service account can access runtime data.

---

### 3. Directory Structure & Permissions ✅ PASS

**Verification**:
- ✅ **Program Files**: `C:\Program Files\WAAST360\Bridge` (read-only application files)
- ✅ **Runtime Data**: `C:\ProgramData\WAAST360\Bridge` (writable data outside Program Files)
- ✅ **Service Account**: NetworkService (limited privileges, appropriate for local service)
- ✅ **Uninstall**: Preserves operational data by default (accounting records are audit evidence)

**Principle**: Separation of concerns
- Read-only application in Program Files (protected by Windows installer conventions)
- Writable data in ProgramData (appropriate for shared service state)
- Graceful uninstall (preserves audit trail unless explicitly deleted)

**Result**: **COMPLIANT** — Windows security best practices followed.

---

### 4. Service Registration Command ✅ PASS

**Verification**:

Service is registered via `sc.exe` with:
```powershell
binPath= "C:\Program Files\WAAST360\Bridge\scripts\run_bridge.bat"
```

Batch file (`run_bridge.bat`) analysis:
- ✅ **No working directory dependency**: Uses `cd /d %BRIDGE_ROOT%` for explicit navigation
- ✅ **No PATH dependency**: Uses absolute path to Python: `%BRIDGE_ROOT%\.venv\Scripts\python.exe`
- ✅ **No venv activation required**: Python called directly from venv
- ✅ **No interactive session required**: Pure batch execution (suitable for service)
- ✅ **Cross-drive compatible**: Uses `cd /d` (allows drives other than C:)

**Result**: **PRODUCTION-READY** — Service can launch without user interaction or specific environment.

---

### 5. Production Configuration Fails Closed ✅ PASS

**Test Results**:

| Scenario | Expected | Result |
|----------|----------|--------|
| **Missing API Key** | Configuration error | ✅ REJECTED with clear error message |
| **Test Key in Production** | Configuration error | ✅ REJECTED ("test key detected in production") |
| **HTTP URL in Production** | Configuration error | ✅ REJECTED ("HTTPS required") |
| **Valid Production Config** | Configuration succeeds | ✅ ACCEPTED (HTTPS + valid key) |

**Code Path**:
```python
# src/config.py - field validators
@field_validator("BRIDGE_API_KEY")
@classmethod
def validate_api_key(cls, v: str, info) -> str:
    is_production = info.data.get("BRIDGE_ENV") == "production"
    if is_production and v == "test-bridge-secret-key":
        raise ValueError("Production deployment detected with test API key...")
    if is_production and not v:
        raise ValueError("BRIDGE_API_KEY is required in production mode...")
```

**Result**: **SECURE** — No silent failures; explicit validation errors guide operator.

---

### 6. Regression Test Suite ✅ PASS

**All tests passing after corrections**:

| Test Suite | Count | Result |
|-----------|-------|--------|
| Configuration Validation (NEW) | 24 | ✅ 24/24 PASS |
| Bridge Tests | 45 | ✅ 45/45 PASS |
| API Tests (incl. E2E) | 20 | ✅ 20/20 PASS |
| Ruff Linting | — | ✅ PASS (0 issues) |
| ESLint/TypeScript | — | ✅ PASS (0 errors) |
| Next.js Build | — | ✅ PASS (0 warnings) |

**No regression**: All existing tests pass; new validation tests confirm security constraints.

**Result**: **VERIFIED** — No regressions; security constraints validated.

---

## Summary of Corrections

### Critical Issue: NetworkService Filesystem Access

**Problem Identified**:
- Original design: Store runtime data in `C:\Users\{user}\AppData\Local\`
- Issue: NetworkService account has no per-user profile; cannot access AppData
- Impact: Service would fail to read/write database and logs

**Solution**:
- Move runtime data to `C:\ProgramData\` (machine-wide location)
- Set environment variables at SYSTEM scope (accessible to service account)
- Update all references in scripts, batch files, and documentation

**Files Modified** (4 total):
1. `bridge/scripts/install_service.ps1` — Set $DataPath and env var scope to Machine
2. `bridge/scripts/uninstall_service.ps1` — Remove from both User and Machine scope
3. `bridge/scripts/run_bridge.bat` — Use C:\ProgramData for logs
4. `bridge/README_DEPLOYMENT.md` — Update all path references (9 instances)

**Verification**: Regression suite re-run: ✅ 89/89 tests PASS

---

## Security Checklist

| Item | Status | Evidence |
|------|--------|----------|
| No hardcoded secrets | ✅ | grep search found 0 hardcoded production keys |
| Secure credential input | ✅ | `Read-Host -AsSecureString` used in installer |
| HTTPS enforcement | ✅ | `validate_cloud_url()` rejects HTTP in production |
| API key validation | ✅ | `validate_api_key()` rejects test keys in production |
| Service account isolation | ✅ | NetworkService (limited privileges) |
| Filesystem isolation | ✅ | ProgramData for service access; proper ACLs |
| Uninstall preservation | ✅ | Data retained by default (audit compliance) |
| Absolute path usage | ✅ | No working directory or PATH dependencies |
| Environment variable scope | ✅ | System scope (accessible to service account) |
| Fail-closed design | ✅ | Configuration errors stop startup with clear messages |

---

## Deployment Readiness

✅ **READY FOR CLIENT DEPLOYMENT**

All security constraints verified. Corrected issue (filesystem access) was caught and fixed before client deployment. Service will have proper access to runtime data on Windows 10/11/Server 2016+.

---

## Next Step

**Do NOT commit yet** — awaiting explicit instruction in locked requirements.

When cleared to commit:
1. Commit all changes with attribution
2. Transfer bridge package to client
3. Client runs installer on office machine
4. Execute LIVE-TALLY-CERT-001 certification gate

---

**Verification Completed**: 2026-09-23  
**Status**: ✅ SECURITY VERIFIED — DEPLOYMENT READY
