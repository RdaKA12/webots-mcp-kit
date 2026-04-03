[CmdletBinding()]
param(
    [string]$PackageSpec = "webots-mcp-kit",
    [switch]$Upgrade
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host "[install] $Message"
}

function Write-Advice {
    param([string]$Message)
    Write-Host "[next] $Message"
}

function Get-CommandTail {
    param([string[]]$CommandParts)

    if ($CommandParts.Length -le 1) {
        return @()
    }
    return $CommandParts[1..($CommandParts.Length - 1)]
}

function Resolve-PythonCommand {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return @($pythonCommand.Source)
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @($pyLauncher.Source, "-3")
    }

    throw "Python was not found on PATH. Install Python 3.11+ first, then rerun this script."
}

function Invoke-Python {
    param(
        [string[]]$PythonCommand,
        [string[]]$Arguments
    )

    & $PythonCommand[0] @(Get-CommandTail -CommandParts $PythonCommand) @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($PythonCommand -join ' ') $($Arguments -join ' ')"
    }
}

function Get-PythonInfo {
    param([string[]]$PythonCommand)

    $script = @'
import json
import sys
payload = {
    'major': sys.version_info.major,
    'minor': sys.version_info.minor,
    'micro': sys.version_info.micro,
    'executable': sys.executable,
}
print(json.dumps(payload))
'@
    $raw = & $PythonCommand[0] @(Get-CommandTail -CommandParts $PythonCommand) -c $script
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to query Python version."
    }
    return $raw | ConvertFrom-Json
}

function Ensure-Pipx {
    param([string[]]$PythonCommand)

    Write-Step "Checking pipx availability"
    & $PythonCommand[0] @(Get-CommandTail -CommandParts $PythonCommand) -m pipx --version *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Step "Installing pipx into the current user profile"
        $null = Invoke-Python -PythonCommand $PythonCommand -Arguments @("-m", "pip", "install", "--user", "pipx")
    }

    Write-Step "Ensuring pipx is on PATH for future shells"
    $null = Invoke-Python -PythonCommand $PythonCommand -Arguments @("-m", "pipx", "ensurepath")

    if ($env:PIPX_BIN_DIR) {
        return $env:PIPX_BIN_DIR
    }

    $binDirOutput = & $PythonCommand[0] @(Get-CommandTail -CommandParts $PythonCommand) -m pipx environment --value PIPX_BIN_DIR 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $binDirOutput) {
        $fallbackBin = Join-Path $HOME ".local\bin"
        if (Test-Path -LiteralPath (Split-Path -Parent $fallbackBin)) {
            return $fallbackBin
        }
        throw "Unable to resolve the pipx bin directory."
    }
    $binDir = (($binDirOutput | Where-Object { $_ -and $_.Trim() }) | Select-Object -Last 1).Trim()
    if (-not $binDir) {
        throw "Unable to resolve the pipx bin directory."
    }
    return $binDir
}

function Install-PackageWithPipx {
    param(
        [string[]]$PythonCommand,
        [string]$PackageSpec,
        [switch]$Upgrade
    )

    if ($Upgrade) {
        Write-Step "Upgrading $PackageSpec through pipx"
        Invoke-Python -PythonCommand $PythonCommand -Arguments @("-m", "pipx", "upgrade", "--install", $PackageSpec)
        return
    }

    Write-Step "Installing $PackageSpec through pipx"
    & $PythonCommand[0] @(Get-CommandTail -CommandParts $PythonCommand) -m pipx install $PackageSpec
    if ($LASTEXITCODE -eq 0) {
        return
    }

    throw "pipx install failed. If the package is already installed, rerun this script with -Upgrade."
}

function Test-WebotsDiscovery {
    $candidatePaths = @()
    if ($env:WEBOTS_HOME) {
        $candidatePaths += $env:WEBOTS_HOME
    }
    $candidatePaths += "C:\Program Files\Webots"

    foreach ($candidate in $candidatePaths) {
        if (-not $candidate) {
            continue
        }
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$verifyScript = Join-Path $PSScriptRoot "verify_install.ps1"
$troubleshootingDoc = Join-Path $repoRoot "docs\troubleshooting.md"

try {
    $pythonCommand = Resolve-PythonCommand
    $pythonInfo = Get-PythonInfo -PythonCommand $pythonCommand
    if ($pythonInfo.major -lt 3 -or ($pythonInfo.major -eq 3 -and $pythonInfo.minor -lt 11)) {
        throw "Python 3.11+ is required. Found $($pythonInfo.major).$($pythonInfo.minor).$($pythonInfo.micro)."
    }

    Write-Step "Using Python $($pythonInfo.major).$($pythonInfo.minor).$($pythonInfo.micro) at $($pythonInfo.executable)"
    $pipxBinDir = Ensure-Pipx -PythonCommand $pythonCommand
    Install-PackageWithPipx -PythonCommand $pythonCommand -PackageSpec $PackageSpec -Upgrade:$Upgrade

    $webotsHome = Test-WebotsDiscovery
    if ($webotsHome) {
        Write-Step "Detected Webots at $webotsHome"
    } else {
        Write-Host ""
        Write-Host "Webots was not detected during install."
        Write-Host "Likely cause: Webots R2025a is not installed yet, or WEBOTS_HOME is not set for this shell."
        Write-Advice "Install Webots R2025a, or set the current shell with: `$env:WEBOTS_HOME = 'C:\Program Files\Webots'"
        Write-Advice "Then run: powershell -ExecutionPolicy Bypass -File `"$verifyScript`""
        Write-Advice "Troubleshooting: $troubleshootingDoc"
    }

    Write-Host ""
    Write-Host "Install finished."
    Write-Advice "If `webots-kit` is not available in this shell, start a new PowerShell window or add this path for the current session: `$env:PATH = `"$pipxBinDir;`$env:PATH`""
    Write-Advice "Then run: powershell -ExecutionPolicy Bypass -File `"$verifyScript`""
}
catch {
    Write-Host ""
    Write-Host "Install failed."
    Write-Host "Likely cause: $($_.Exception.Message)"
    Write-Advice "Fix the problem above, then rerun: powershell -ExecutionPolicy Bypass -File `"$PSScriptRoot\install.ps1`" -PackageSpec `"$PackageSpec`""
    Write-Advice "Troubleshooting: $troubleshootingDoc"
    exit 1
}
