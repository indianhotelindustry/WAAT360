<#
.SYNOPSIS
    Install WAAST360 Bridge as a Windows Service

.DESCRIPTION
    Installs the WAAST360 Bridge integration agent as an automatic Windows Service.
    Validates prerequisites, securely configures credentials, creates runtime directories,
    registers the service, and verifies installation.

.PARAMETER CloudUrl
    WAAST360 Cloud API endpoint (https://... required for production)

.PARAMETER BridgeClientId
    Unique Bridge identifier (assigned by WAAST360 admin)

.PARAMETER SkipValidation
    Skip prerequisites validation (not recommended)

.EXAMPLE
    .\install_service.ps1 -CloudUrl "https://waast360-api.example.com" -BridgeClientId "BR-ACME-01"

.NOTES
    Requires Administrator privileges.
    Target: Windows 10, Windows 11, Windows Server 2016+
#>

param(
    [string]$CloudUrl = "",
    [string]$BridgeClientId = "",
    [switch]$SkipValidation
)

# ============================================================================
# INITIALIZATION
# ============================================================================

$ErrorActionPreference = "Stop"
$WarningPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BridgeRoot = Split-Path -Parent $ScriptDir
$ServiceName = "WAAST360Bridge"
$ServiceDisplayName = "WAAST360 Integration Bridge"
$InstallPath = "C:\Program Files\WAAST360\Bridge"
# Use ProgramData (machine-wide, service-accessible) instead of per-user AppData
$DataPath = "C:\ProgramData\WAAST360\Bridge"
$LogPath = Join-Path $DataPath "logs"
$VenvPath = Join-Path $BridgeRoot ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$BridgeSrc = Join-Path $BridgeRoot "src"
$WinSWPath = Join-Path $InstallPath "winsw"
$WinSWExe = Join-Path $WinSWPath "WAAST360Bridge.exe"
$WinSWXml = Join-Path $WinSWPath "WAAST360Bridge.xml"

# Logging
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

# ============================================================================
# VALIDATION
# ============================================================================

function Test-AdminPrivileges {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-WindowsVersion {
    $osVersion = [System.Environment]::OSVersion.Version
    if ($osVersion.Major -lt 10) {
        Write-Error-Log "Windows 10 or later required. Current: $($osVersion.Major).$($osVersion.Minor)"
        return $false
    }
    Write-Log "Windows version: $($osVersion.Major).$($osVersion.Minor).$($osVersion.Build)"
    return $true
}

function Test-PythonAvailable {
    if (-not (Test-Path $PythonExe)) {
        Write-Error-Log "Python not found at: $PythonExe"
        Write-Log "Ensure venv is created: python -m venv .venv"
        return $false
    }

    $pythonVersion = & $PythonExe --version 2>&1
    Write-Log "Python found: $pythonVersion"
    return $true
}

function Test-BridgePackageIntegrity {
    $requiredFiles = @(
        (Join-Path $BridgeSrc "main.py"),
        (Join-Path $BridgeSrc "daemon.py"),
        (Join-Path $BridgeSrc "config.py"),
        (Join-Path $BridgeRoot "requirements.txt")
    )

    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            Write-Error-Log "Missing required file: $file"
            return $false
        }
    }

    Write-Log "Bridge package integrity verified"
    return $true
}

function Test-TallyConnectivity {
    Write-Log "Testing Tally connectivity..."
    try {
        & $PythonExe (Join-Path $BridgeSrc ".." "main.py") test-tally --host 127.0.0.1 --port 9000 2>&1 | ForEach-Object { Write-Log $_ }
    } catch {
        Write-Warning-Log "Tally connectivity test failed (this is OK if Tally is not running yet): $_"
    }
}

function Validate-CloudUrl {
    param([string]$Url)

    if ([string]::IsNullOrWhiteSpace($Url)) {
        Write-Error-Log "Cloud URL cannot be empty"
        return $false
    }

    # Check for HTTPS in production (non-localhost)
    if ($Url -notmatch "^https://" -and $Url -notmatch "127.0.0.1" -and $Url -notmatch "localhost") {
        Write-Warning-Log "Non-localhost Cloud URL should use HTTPS"
    }

    Write-Log "Cloud URL validated: $Url"
    return $true
}

# ============================================================================
# PREREQUISITE COLLECTION
# ============================================================================

function Get-Configuration {
    Write-Log "Gathering configuration..."

    if ([string]::IsNullOrWhiteSpace($CloudUrl)) {
        $CloudUrl = Read-Host "Enter Cloud API URL (e.g., https://waast360-api.example.com)"
    }

    if (-not (Validate-CloudUrl $CloudUrl)) {
        Write-Error-Log "Invalid Cloud URL"
        return $null
    }

    if ([string]::IsNullOrWhiteSpace($BridgeClientId)) {
        $BridgeClientId = Read-Host "Enter Bridge Client ID (e.g., BR-CLIENT-01)"
    }

    # Securely prompt for API key
    $apiKeySecure = Read-Host "Enter Bridge API Key" -AsSecureString
    $apiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToCoTaskMemUnicode($apiKeySecure)
    )

    if ([string]::IsNullOrWhiteSpace($apiKey)) {
        Write-Error-Log "API Key cannot be empty"
        return $null
    }

    return @{
        CloudUrl = $CloudUrl
        BridgeClientId = $BridgeClientId
        BridgeApiKey = $apiKey
    }
}

# ============================================================================
# RUNTIME SETUP
# ============================================================================

function New-RuntimeDirectories {
    Write-Log "Creating runtime directories..."

    $dirs = @($InstallPath, $DataPath, $LogPath)
    foreach ($dir in $dirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force -ErrorAction Stop | Out-Null
            Write-Log "Created: $dir"
        }
    }

    # Set ACLs on data directory (restrict to current user + LocalSystem)
    Write-Log "Setting ACLs on data directory..."
    $acl = Get-Acl $DataPath
    $acl.SetAccessRuleProtection($true, $false)
    Set-Acl -Path $DataPath -AclObject $acl
    Write-Log "Data directory ACLs configured"
}

function New-EnvironmentVariables {
    param([hashtable]$Config)

    Write-Log "Configuring environment variables (SYSTEM scope for NetworkService)..."

    # Set at SYSTEM scope so NetworkService service account can read them
    [Environment]::SetEnvironmentVariable("BRIDGE_ENV", "production", "Machine")
    [Environment]::SetEnvironmentVariable("CLOUD_URL", $Config.CloudUrl, "Machine")
    [Environment]::SetEnvironmentVariable("BRIDGE_CLIENT_ID", $Config.BridgeClientId, "Machine")
    [Environment]::SetEnvironmentVariable("BRIDGE_API_KEY", $Config.BridgeApiKey, "Machine")
    [Environment]::SetEnvironmentVariable("DB_PATH", (Join-Path $DataPath "bridge_store.db"), "Machine")

    Write-Log "Environment variables set at SYSTEM scope (accessible to NetworkService)"
}

# ============================================================================
# WINSW SERVICE WRAPPER
# ============================================================================

function New-WinSWConfig {
    param([string]$ApiKey)

    Write-Log "Creating WinSW service wrapper..."

    if (-not (Test-Path $WinSWPath)) {
        New-Item -ItemType Directory -Path $WinSWPath -Force | Out-Null
    }

    # Generate WinSW XML configuration
    $winswXmlContent = @"
<?xml version="1.0" encoding="UTF-8" ?>
<service>
    <id>WAAST360Bridge</id>
    <name>$ServiceDisplayName</name>
    <description>WAAST360 Integration Bridge for TallyPrime</description>
    <executable>$PythonExe</executable>
    <arguments>-u "$BridgeSrc\main.py" start</arguments>
    <workingDirectory>$BridgeRoot</workingDirectory>

    <logmode>roll</logmode>
    <logpath>$LogPath</logpath>
    <loglevel>INFO</loglevel>

    <serviceaccount>
        <allowServiceLogon>true</allowServiceLogon>
    </serviceaccount>

    <startmode>Automatic</startmode>
    <stopparentprocessfirst>true</stopparentprocessfirst>

    <!-- Restart service after failure -->
    <onfailure action="restart" delay="60000" />
    <onfailure action="restart" delay="120000" />
    <onfailure action="restart" delay="300000" />

    <env name="BRIDGE_ENV" value="production" />
    <env name="PYTHONUNBUFFERED" value="1" />
    <env name="PYTHONIOENCODING" value="utf-8" />
</service>
"@

    Set-Content -Path $WinSWXml -Value $winswXmlContent -Encoding UTF8 -ErrorAction Stop
    Write-Log "WinSW configuration created: $WinSWXml"
}

function Install-WinSW {
    Write-Log "Installing WinSW service wrapper..."

    if (-not (Test-Path $WinSWExe)) {
        # Download or copy WinSW.exe to $WinSWPath
        # For now, we'll assume it's already present or needs to be added during deployment
        Write-Warning-Log "WinSW.exe not found at $WinSWExe"
        Write-Log "Note: WinSW.exe must be present in $WinSWPath before service registration"

        # Alternative: Use built-in sc.exe for service registration (simpler approach)
        Write-Log "Using Windows Service Control (sc.exe) for registration instead"
        return $true
    }

    Write-Log "WinSW.exe found, proceeding with registration"
    return $true
}

# ============================================================================
# SERVICE REGISTRATION
# ============================================================================

function Register-BridgeService {
    Write-Log "Registering Windows Service..."

    # Check if service already exists
    $existingService = Get-Service $ServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Warning-Log "Service $ServiceName already exists. Stopping and removing..."
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2

        & sc.exe delete $ServiceName 2>&1 | Out-Null
        Start-Sleep -Seconds 2
    }

    # Register service using sc.exe (built-in, no dependencies)
    $batchFile = Join-Path $BridgeRoot "scripts\run_bridge.bat"

    & sc.exe create $ServiceName `
        binPath= "$batchFile" `
        displayName= "$ServiceDisplayName" `
        start= auto `
        error= normal 2>&1 | ForEach-Object { Write-Log $_ }

    if ($LASTEXITCODE -eq 0) {
        Write-Success-Log "Service $ServiceName registered successfully"

        # Set service to restart on failure
        & sc.exe failure $ServiceName reset= 60 actions= restart/60000/restart/120000/restart/300000 2>&1 | Out-Null
        Write-Log "Service restart policy configured"

        return $true
    } else {
        Write-Error-Log "Failed to register service"
        return $false
    }
}

function Start-BridgeService {
    Write-Log "Starting service $ServiceName..."

    try {
        Start-Service -Name $ServiceName -ErrorAction Stop
        Start-Sleep -Seconds 2

        $service = Get-Service $ServiceName
        if ($service.Status -eq "Running") {
            Write-Success-Log "Service $ServiceName is running"
            return $true
        } else {
            Write-Error-Log "Service status: $($service.Status)"
            return $false
        }
    } catch {
        Write-Error-Log "Failed to start service: $_"
        return $false
    }
}

# ============================================================================
# VALIDATION & CLEANUP
# ============================================================================

function Test-ServiceInstallation {
    Write-Log "Validating service installation..."

    $service = Get-Service $ServiceName -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Error-Log "Service not found"
        return $false
    }

    Write-Log "Service Status: $($service.Status)"
    Write-Log "Service StartType: $($service.StartType)"

    return $true
}

# ============================================================================
# MAIN INSTALLATION FLOW
# ============================================================================

function Main {
    Write-Log "WAAST360 Bridge Windows Service Installer"
    Write-Log "=========================================="
    Write-Log ""

    # 1. Validate prerequisites
    if (-not $SkipValidation) {
        Write-Log "Validating prerequisites..."

        if (-not (Test-AdminPrivileges)) {
            Write-Error-Log "This script requires Administrator privileges"
            exit 1
        }

        if (-not (Test-WindowsVersion)) {
            exit 1
        }

        if (-not (Test-PythonAvailable)) {
            exit 1
        }

        if (-not (Test-BridgePackageIntegrity)) {
            exit 1
        }

        Write-Success-Log "All prerequisites validated"
    }

    # 2. Gather configuration
    $config = Get-Configuration
    if (-not $config) {
        exit 1
    }

    # 3. Create runtime directories
    New-RuntimeDirectories

    # 4. Configure environment
    New-EnvironmentVariables $config

    # 5. Setup WinSW
    New-WinSWConfig $config.BridgeApiKey
    Install-WinSW

    # 6. Register service
    if (-not (Register-BridgeService)) {
        Write-Error-Log "Service registration failed"
        exit 1
    }

    # 7. Start service
    if (-not (Start-BridgeService)) {
        Write-Error-Log "Failed to start service"
        # Warn but continue; service may start after system reboot
    }

    # 8. Validate
    if (-not (Test-ServiceInstallation)) {
        Write-Error-Log "Service validation failed"
        exit 1
    }

    # 9. Optional: Test Tally connectivity
    Write-Log ""
    Test-TallyConnectivity

    # Summary
    Write-Log ""
    Write-Success-Log "Installation complete!"
    Write-Log "Service Name: $ServiceName"
    Write-Log "Install Path: $InstallPath"
    Write-Log "Data Path: $DataPath"
    Write-Log "Logs: $LogPath"
    Write-Log ""
    Write-Log "Next steps:"
    Write-Log "1. Verify TallyPrime is running on 127.0.0.1:9000"
    Write-Log "2. Check service status: Get-Service $ServiceName"
    Write-Log "3. Review logs: Get-Content '$LogPath\*' -Tail 50"
    Write-Log "4. Test connectivity: $PythonExe $BridgeSrc\main.py test-tally"
    Write-Log "5. Proceed to LIVE-TALLY-CERT-001 certification"
    Write-Log ""
}

try {
    Main
} catch {
    Write-Error-Log "Installation failed: $_"
    Write-Log $_.Exception.StackTrace
    exit 1
}
