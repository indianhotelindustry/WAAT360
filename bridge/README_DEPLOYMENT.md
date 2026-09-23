# WAAST360 Bridge Windows Deployment Guide

**Version**: 1.0  
**Last Updated**: 2026-09-23  
**Target**: Windows 10, Windows 11, Windows Server 2016+

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)
7. [Security](#security)
8. [Uninstallation](#uninstallation)
9. [Next Steps: LIVE-TALLY-CERT-001](#next-steps-live-tally-cert-001)

---

## Overview

The WAAST360 Bridge is a local Windows service that connects TallyPrime to the WAAST360 Cloud accounting platform. It:

- Runs continuously in the background as a Windows Service
- Polls the Cloud for pending voucher posting jobs
- Executes posting reconciliation against local TallyPrime
- Maintains a durable local queue for offline resilience
- Provides detailed logging and audit trails

**Key Points**:
- Bridge must run on the same Windows machine as TallyPrime
- No public port exposure required (outbound HTTPS polling only)
- Automatic service restart on failure
- Supports both JSON (TallyPrime 7.0+) and XML adapters

---

## Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Windows 10 / Server 2016 | Windows 11 / Server 2022 |
| **Admin** | Required for installation | Yes |
| **Python** | 3.12 | 3.14 |
| **TallyPrime** | Active company loaded | Connected on 127.0.0.1:9000 |
| **Firewall** | Outbound HTTPS allowed | Port 443 open to Cloud endpoint |
| **Disk Space** | 500 MB | 1 GB (for logs/queue growth) |

### Pre-Installation Checklist

- [ ] Windows 10 or later confirmed
- [ ] Administrator privileges available
- [ ] Python 3.12+ installed OR provided by installer
- [ ] TallyPrime running with HTTP/ODBC enabled (see [TallyPrime Configuration](#tallyprime-configuration))
- [ ] At least one company loaded in TallyPrime
- [ ] Network access to WAAST360 Cloud API (HTTPS)
- [ ] Firewall permits loopback connections to 127.0.0.1:9000

### TallyPrime Configuration

Before installing the Bridge, ensure TallyPrime is configured for HTTP/ODBC access:

1. **Open TallyPrime** and ensure at least one company is loaded (Books From date must be set)
2. **Press F12** (Configuration) → **Advanced Configuration**
3. **Set the following**:
   - **Tally is acting as**: `Both` (or `Server`)
   - **Enable ODBC**: `Yes`
   - **Port**: `9000` (default)
4. **Accept** and close configuration
5. **Restart TallyPrime** if prompted
6. **Verify** by navigating to `http://127.0.0.1:9000` in a browser (you should see XML response or Tally interface)

---

## Installation

### Step 1: Download and Extract Bridge Package

1. Download the WAAST360 Bridge package from your deployment provider
2. Extract to a temporary location, e.g., `C:\Temp\WAAST360-Bridge`
3. Open PowerShell as Administrator

```powershell
# Navigate to Bridge directory
cd C:\Temp\WAAST360-Bridge\bridge
```

### Step 2: Verify Package Integrity

Ensure the Bridge package contains:
- `scripts\install_service.ps1` — Installation script
- `scripts\uninstall_service.ps1` — Uninstaller script
- `scripts\run_bridge.bat` — Launcher
- `src\main.py`, `src\daemon.py`, `src\config.py` — Core Bridge code
- `requirements.txt` — Python dependencies
- `.env.example` — Configuration template

### Step 3: Set Execution Policy (One-Time)

In PowerShell (Admin):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 4: Run Installation Script

In PowerShell (Admin), from the Bridge directory:

```powershell
.\scripts\install_service.ps1
```

The script will prompt you for:

1. **Cloud API URL**: Your WAAST360 endpoint (e.g., `https://waast360-api.example.com`)
2. **Bridge Client ID**: Your unique identifier (assigned by WAAST360, e.g., `BR-ACME-01`)
3. **Bridge API Key**: Secure credential (provided by WAAST360 admin)

**Important**: The API key is entered securely and stored in Windows environment variables.

### Step 5: Verify Installation

```powershell
# Check service status
Get-Service WAAST360Bridge | Select-Object Status, StartType

# Should output:
# Status StartType
# ------ ---------
# Running Automatic
```

If status is "Stopped", see [Troubleshooting](#troubleshooting).

---

## Configuration

### Environment Variables

The installer sets environment variables in your user profile:

| Variable | Purpose | Example |
|----------|---------|---------|
| `BRIDGE_ENV` | Deployment mode | `production` |
| `CLOUD_URL` | WAAST360 Cloud API | `https://waast360-api.example.com` |
| `BRIDGE_CLIENT_ID` | Unique Bridge identifier | `BR-ACME-01` |
| `BRIDGE_API_KEY` | API authentication key | `(secure credential)` |
| `DB_PATH` | SQLite database path | `C:\Users\{user}\AppData\Local\WAAST360\Bridge\bridge_store.db` |

### Runtime Locations

- **Installation**: `C:\Program Files\WAAST360\Bridge` (read-only)
- **Data/Logs**: `C:\ProgramData\WAAST360\Bridge` (machine-wide, service-accessible)
- **Database**: `C:\ProgramData\WAAST360\Bridge\bridge_store.db`
- **Logs**: `C:\ProgramData\WAAST360\Bridge\logs\`

### Manual Configuration Override (`.env`)

For advanced users, create a `.env` file in the Bridge directory to override environment variables:

```bash
# .env (optional - for local dev/testing only)
BRIDGE_ENV=production
CLOUD_URL=https://your-api.example.com
BRIDGE_CLIENT_ID=BR-ACME-01
BRIDGE_API_KEY=your-key-here
TALLY_HOST=127.0.0.1
TALLY_PORT=9000
POLL_INTERVAL_SECONDS=5.0
```

**Security**: Never commit `.env` to version control or share with others.

---

## Verification

### 1. Service Status

```powershell
# Check service is running
Get-Service WAAST360Bridge

# View recent logs
Get-EventLog -LogName System -Source WAAST360Bridge -Newest 10
```

### 2. Test Tally Connectivity

From PowerShell:

```powershell
cd "C:\Program Files\WAAST360\Bridge"
.\.venv\Scripts\python.exe src\main.py test-tally --host 127.0.0.1 --port 9000
```

**Expected Output**:
```
Online: True
Version: TallyPrime 7.0
Response Time: 150 ms

--- CAPABILITIES ---
  supports_json: True
  supports_xml: True
```

### 3. Test Company Discovery

```powershell
.\.venv\Scripts\python.exe src\main.py discover --host 127.0.0.1 --port 9000
```

**Expected Output**: List of companies currently loaded in TallyPrime with GUIDs and financial years.

### 4. Review Service Logs

Log files are written to: `C:\Users\{username}\AppData\Local\WAAST360\Bridge\logs\`

```powershell
# View latest log
Get-Content -Path "$env:LOCALAPPDATA\WAAST360\Bridge\logs\*" -Tail 50
```

Look for lines like:
```
[2026-09-23 10:15:30] [INFO] Bridge initialized
[2026-09-23 10:15:31] [INFO] Starting WAAST360 Bridge daemon (BR-ACME-01)
[2026-09-23 10:15:35] [INFO] Cloud heartbeat sent: status=ONLINE
```

### 5. Dashboard Check (Web UI)

If you have access to the WAAST360 Cloud Dashboard:

1. Log in to the Dashboard
2. Navigate to **System → Bridges**
3. Verify your Bridge appears with status **ONLINE** and recent heartbeat timestamp

---

## Troubleshooting

### Service Won't Start

**Symptom**: `Get-Service WAAST360Bridge` shows status `Stopped`

**Diagnosis**:
1. Check if Python is available:
   ```powershell
   Test-Path "C:\Program Files\WAAST360\Bridge\.venv\Scripts\python.exe"
   ```

2. Review logs:
   ```powershell
   Get-Content "$env:LOCALAPPDATA\WAAST360\Bridge\logs\*" -Tail 50
   ```

3. Try manual start:
   ```powershell
   cd "C:\Program Files\WAAST360\Bridge"
   .\scripts\run_bridge.bat
   ```

**Solutions**:
- **Python not found**: Reinstall Python 3.12+ or run installer again
- **Missing credentials**: Ensure `BRIDGE_API_KEY` environment variable is set (restart PowerShell after install)
- **Tally offline**: Verify TallyPrime is running on 127.0.0.1:9000
- **Invalid CLOUD_URL**: Confirm HTTPS and endpoint is reachable

### Tally Connectivity Error

**Symptom**: `Online: False` when running `test-tally`

**Solutions**:
1. Verify TallyPrime is running:
   ```powershell
   # Open browser and navigate to:
   # http://127.0.0.1:9000
   ```

2. Check F12 configuration in TallyPrime:
   - Ensure "Tally is acting as": `Both`
   - Ensure "Enable ODBC": `Yes`
   - Port: `9000`

3. Check Windows Firewall:
   ```powershell
   # Allow loopback connections
   netsh advfirewall firewall add rule name="Tally Bridge Loopback" dir=in action=allow program="C:\Program Files\WAAST360\Bridge\.venv\Scripts\python.exe" remoteip=127.0.0.1
   ```

### Cloud API Connection Failed

**Symptom**: `Cloud heartbeat failed` in logs

**Solutions**:
1. Verify Cloud URL:
   ```powershell
   # Check if reachable
   curl -I https://your-waast360-api.example.com
   ```

2. Verify credentials:
   ```powershell
   # Check environment variable
   Write-Output $env:BRIDGE_API_KEY
   ```

3. Check firewall outbound rules:
   ```powershell
   # Ensure HTTPS (port 443) is open outbound
   Test-NetConnection -ComputerName your-waast360-api.example.com -Port 443
   ```

### Permission Denied on Database

**Symptom**: `[ERROR] sqlite3.OperationalError: attempt to write a readonly database`

**Solutions**:
1. Verify directory permissions:
   ```powershell
   icacls "$env:LOCALAPPDATA\WAAST360\Bridge" /grant "%USERNAME%:(OI)(CI)F"
   ```

2. Restart service:
   ```powershell
   Restart-Service WAAST360Bridge
   ```

### High Memory Usage

**Symptom**: Python process consumes significant memory

**Solutions**:
1. Check queue size:
   ```powershell
   # Inspect local database
   cd "$env:LOCALAPPDATA\WAAST360\Bridge"
   # Large bridge_store.db may indicate queue backlog
   (Get-Item bridge_store.db).Length / 1MB
   ```

2. Check Cloud API for stuck jobs (contact WAAST360 admin)

3. Review logs for retry loops

---

## Security

### Credential Protection

- **API Key** is stored as Windows environment variable (encrypted via DPAPI if BitLocker enabled)
- **Never share** your `BRIDGE_API_KEY` via email or chat
- **Never commit** `.env` files with credentials to version control

### Network Security

- Bridge only initiates **outbound HTTPS** connections to WAAST360 Cloud
- **Tally port 9000** is NOT exposed to the Internet
- Firewall should allow **outbound 443** (HTTPS) only
- Loopback connections (127.0.0.1) are trusted

### File Permissions

- Bridge data directory `C:\Users\{user}\AppData\Local\WAAST360\Bridge` is restricted to current user
- SQLite database `bridge_store.db` is not encrypted (relies on file system permissions)
- Logs may contain voucher references; store securely

### Compliance

- Bridge maintains audit trail of all voucher postings
- Read-back verification proves Tally acceptance
- No offline posting is final until verified against live Tally
- All events logged for forensic analysis

---

## Uninstallation

### Option 1: Clean Uninstall (Preserve Data)

```powershell
# Run as Administrator
cd "C:\Program Files\WAAST360\Bridge"
.\scripts\uninstall_service.ps1
```

This will:
- Stop the service
- Unregister Windows Service
- Remove environment variables
- **Preserve** runtime data (logs, database) for audit purposes

### Option 2: Complete Removal (Delete All)

```powershell
.\scripts\uninstall_service.ps1 -RemoveData
```

This will:
- Stop the service
- Unregister Windows Service
- Remove environment variables
- **Delete** all runtime data

**Warning**: Deleting runtime data will remove your local queue and logs. Only do this if you have backed up necessary audit evidence.

### Manual Cleanup

If scripts fail, manually remove:

```powershell
# Remove service
sc.exe delete WAAST360Bridge

# Remove environment variables
[Environment]::SetEnvironmentVariable("BRIDGE_ENV", $null, "User")
[Environment]::SetEnvironmentVariable("CLOUD_URL", $null, "User")
[Environment]::SetEnvironmentVariable("BRIDGE_CLIENT_ID", $null, "User")
[Environment]::SetEnvironmentVariable("BRIDGE_API_KEY", $null, "User")

# Remove installation directory (optional)
Remove-Item "C:\Program Files\WAAST360\Bridge" -Recurse -Force

# Remove data directory (optional)
Remove-Item "$env:LOCALAPPDATA\WAAST360\Bridge" -Recurse -Force
```

---

## Next Steps: LIVE-TALLY-CERT-001

Once the Bridge service is installed and verified, you are ready for live TallyPrime certification.

### Certification Objectives

The `LIVE-TALLY-CERT-001` gate verifies:

1. ✅ **Connectivity**: Bridge reaches TallyPrime on 127.0.0.1:9000
2. ✅ **Company Discovery**: Tally companies are discovered and synced to Cloud
3. ✅ **Company Mapping**: Tally company is linked to WAAST360 Company in Dashboard
4. ✅ **Live Posting**: Test voucher is posted to Tally via Bridge
5. ✅ **Read-Back Verification**: Voucher is confirmed in Tally and Cloud

### Pre-Certification Verification

Before proceeding, confirm:

```powershell
# 1. Service running
Get-Service WAAST360Bridge | Select-Object Status

# 2. Tally online
.\.venv\Scripts\python.exe src\main.py test-tally

# 3. Companies discovered
.\.venv\Scripts\python.exe src\main.py discover

# 4. Cloud reachable
Test-NetConnection -ComputerName your-waast360-api.example.com -Port 443
```

### Certification Steps

See: `docs/testing/LIVE_TALLY_CERTIFICATION_GATE.md`

The certification will execute:
1. Connectivity & capabilities probe
2. Live company discovery and sync
3. Company association in WAAST360 Dashboard
4. Real voucher posting and read-back verification

---

## Support

For issues or questions:

1. **Check Logs**: `$env:LOCALAPPDATA\WAAST360\Bridge\logs\`
2. **Review Troubleshooting** section above
3. **Verify Prerequisites**: Confirm TallyPrime configuration
4. **Contact WAAST360 Admin**: Provide logs and error messages

---

## Appendix: WinSW Service Wrapper

The Bridge uses WinSW (Windows Service Wrapper) to run as a Windows Service. Configuration is at:

`C:\Program Files\WAAST360\Bridge\winsw\WAAST360Bridge.xml`

Manual service management:

```powershell
# Start
Start-Service WAAST360Bridge

# Stop
Stop-Service WAAST360Bridge

# Restart
Restart-Service WAAST360Bridge

# View logs
Get-Content "$env:LOCALAPPDATA\WAAST360\Bridge\logs\*" -Tail 100

# View service properties
Get-Service WAAST360Bridge | Format-List *

# Set to manual start (not recommended)
Set-Service -Name WAAST360Bridge -StartupType Manual
```

---

**End of Deployment Guide**
