<#
.SYNOPSIS
    Uninstall WAAST360 Bridge Windows Service

.DESCRIPTION
    Cleanly removes the WAAST360 Bridge service while preserving operational data.
    Offers options to retain or delete accounting/queue data for audit compliance.

.PARAMETER RemoveData
    Also remove runtime data (database, logs). Use with caution for complete cleanup.

.EXAMPLE
    .\uninstall_service.ps1
    .\uninstall_service.ps1 -RemoveData

.NOTES
    Requires Administrator privileges.
#>

param(
    [switch]$RemoveData
)

$ErrorActionPreference = "Stop"

$ServiceName = "WAAST360Bridge"
$ServiceDisplayName = "WAAST360 Integration Bridge"
# Use ProgramData (machine-wide, service-accessible) instead of per-user AppData
$DataPath = "C:\ProgramData\WAAST360\Bridge"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

function Write-Error-Log {
    param([string]$Message)
    Write-Log $Message "ERROR"
}

function Write-Success-Log {
    param([string]$Message)
    Write-Log $Message "SUCCESS"
}

function Write-Warning-Log {
    param([string]$Message)
    Write-Log $Message "WARNING"
}

function Test-AdminPrivileges {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Stop-BridgeService {
    Write-Log "Stopping service $ServiceName..."

    $service = Get-Service $ServiceName -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Warning-Log "Service $ServiceName not found (already removed?)"
        return $true
    }

    if ($service.Status -eq "Running") {
        try {
            Stop-Service -Name $ServiceName -Force -ErrorAction Stop
            Start-Sleep -Seconds 2
            Write-Success-Log "Service stopped"
        } catch {
            Write-Error-Log "Failed to stop service: $_"
            return $false
        }
    } else {
        Write-Log "Service is already stopped"
    }

    return $true
}

function Unregister-BridgeService {
    Write-Log "Unregistering service $ServiceName..."

    try {
        & sc.exe delete $ServiceName 2>&1 | Out-Null
        Start-Sleep -Seconds 2

        $service = Get-Service $ServiceName -ErrorAction SilentlyContinue
        if ($service) {
            Write-Error-Log "Service still exists after deletion attempt"
            return $false
        }

        Write-Success-Log "Service unregistered"
        return $true
    } catch {
        Write-Error-Log "Failed to unregister service: $_"
        return $false
    }
}

function Remove-EnvironmentVariables {
    Write-Log "Removing environment variables (SYSTEM scope)..."

    $vars = @("BRIDGE_ENV", "CLOUD_URL", "BRIDGE_CLIENT_ID", "BRIDGE_API_KEY", "DB_PATH")
    foreach ($var in $vars) {
        # Remove from both User and Machine scope
        [Environment]::SetEnvironmentVariable($var, $null, "User")
        [Environment]::SetEnvironmentVariable($var, $null, "Machine")
    }

    Write-Success-Log "Environment variables removed"
}

function Remove-RuntimeData {
    Write-Log "Preparing to remove runtime data..."
    Write-Log "Data Path: $DataPath"

    if (-not (Test-Path $DataPath)) {
        Write-Log "Data directory not found (already removed?)"
        return $true
    }

    # List contents for confirmation
    Write-Log "Contents of $DataPath :"
    Get-ChildItem -Path $DataPath -Recurse | ForEach-Object {
        Write-Log "  $($_.FullName.Substring($DataPath.Length))"
    }

    # Prompt for confirmation
    $response = Read-Host "Delete this data? (yes/no)"
    if ($response -ne "yes") {
        Write-Log "Data preservation confirmed - runtime files retained"
        return $true
    }

    try {
        Remove-Item -Path $DataPath -Recurse -Force -ErrorAction Stop
        Write-Success-Log "Runtime data removed"
        return $true
    } catch {
        Write-Error-Log "Failed to remove data: $_"
        return $false
    }
}

function Main {
    Write-Log "WAAST360 Bridge Uninstaller"
    Write-Log "============================="
    Write-Log ""

    if (-not (Test-AdminPrivileges)) {
        Write-Error-Log "This script requires Administrator privileges"
        exit 1
    }

    # Confirm uninstall
    Write-Warning-Log "This will uninstall the WAAST360 Bridge service."
    Write-Log "Operational data (database, logs) can be retained for audit purposes."
    Write-Log ""

    $confirm = Read-Host "Proceed with uninstallation? (yes/no)"
    if ($confirm -ne "yes") {
        Write-Log "Uninstallation cancelled"
        exit 0
    }

    # 1. Stop service
    if (-not (Stop-BridgeService)) {
        Write-Error-Log "Failed to stop service"
        exit 1
    }

    # 2. Unregister service
    if (-not (Unregister-BridgeService)) {
        Write-Error-Log "Failed to unregister service"
        exit 1
    }

    # 3. Remove environment variables
    Remove-EnvironmentVariables

    # 4. Handle runtime data
    if ($RemoveData) {
        if (-not (Remove-RuntimeData)) {
            Write-Error-Log "Failed to remove runtime data"
            exit 1
        }
    } else {
        Write-Log ""
        Write-Log "Runtime data preserved at: $DataPath"
        Write-Log "To remove later: Remove-Item -Path '$DataPath' -Recurse -Force"
    }

    Write-Log ""
    Write-Success-Log "Uninstallation complete"
    Write-Log "Bridge service has been removed from Windows"
    Write-Log ""
}

try {
    Main
} catch {
    Write-Error-Log "Uninstallation failed: $_"
    exit 1
}
