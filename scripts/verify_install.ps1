[CmdletBinding()]
param(
    [switch]$Runtime
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    Write-Host "[verify] $Message"
}

function Fail-Verification {
    param(
        [string]$Step,
        [string]$LikelyCause,
        [string]$NextAction
    )

    Write-Host ""
    Write-Host "Verification failed at: $Step"
    Write-Host "Likely cause: $LikelyCause"
    Write-Host "Next action: $NextAction"
    exit 1
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

    throw "Python was not found on PATH."
}

function Resolve-WebotsKitCommand {
    $command = Get-Command webots-kit -ErrorAction SilentlyContinue
    if ($command) {
        return @($command.Source)
    }

    $pythonCommand = Resolve-PythonCommand
    & $pythonCommand[0] @(Get-CommandTail -CommandParts $pythonCommand) -m webots_mcp_kit.cli --version *> $null
    if ($LASTEXITCODE -eq 0) {
        return @($pythonCommand + @("-m", "webots_mcp_kit.cli"))
    }

    throw "webots-kit is not available in this shell."
}

function Invoke-WebotsKitText {
    param(
        [string[]]$Command,
        [string[]]$Arguments,
        [string]$StepName
    )

    Write-Step $StepName
    $output = & $Command[0] @(Get-CommandTail -CommandParts $Command) @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($output -join [Environment]::NewLine)
    }
    return ($output -join [Environment]::NewLine)
}

function Invoke-WebotsKitJson {
    param(
        [string[]]$Command,
        [string[]]$Arguments,
        [string]$StepName
    )

    $raw = Invoke-WebotsKitText -Command $Command -Arguments $Arguments -StepName $StepName
    try {
        return $raw | ConvertFrom-Json
    } catch {
        throw "Expected JSON output but could not parse it. Raw output:`n$raw"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$troubleshootingDoc = Join-Path $repoRoot "docs\troubleshooting.md"
$workspace = Join-Path $env:TEMP ("webots-kit-verify-" + [System.Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $workspace | Out-Null
$controllerPath = Join-Path $workspace "verify_line_follower.py"
$reportPath = Join-Path $workspace "line-follower-report.json"

try {
    $webotsKit = Resolve-WebotsKitCommand
} catch {
    Fail-Verification -Step "command resolution" `
        -LikelyCause "The package is installed but the current shell cannot see the `webots-kit` command yet." `
        -NextAction "Start a new PowerShell window, then rerun this script. If you installed with pipx, run `python -m pipx ensurepath` first. See $troubleshootingDoc"
}

try {
    $versionText = Invoke-WebotsKitText -Command $webotsKit -Arguments @("--version") -StepName "Checking webots-kit version"
    Write-Host $versionText
} catch {
    Fail-Verification -Step "version check" `
        -LikelyCause "The installed package is incomplete or the shell resolved the wrong `webots-kit` command." `
        -NextAction "Reinstall with `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Upgrade`, then rerun this script. See $troubleshootingDoc"
}

try {
    $doctor = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("doctor", "--json") -StepName "Running doctor"
    if ($doctor.status -ne "ready") {
        $runnerMode = $doctor.runtime_readiness.runner_mode.mode
        $nextAction = if ($doctor.status -eq "blocked") {
            "Install Webots R2025a or set `$env:WEBOTS_HOME, then rerun this script. See $troubleshootingDoc"
        } elseif ($runnerMode -eq "windows-service") {
            "Move the runner into an interactive desktop session, then rerun this script. See $troubleshootingDoc"
        } else {
            "Open $troubleshootingDoc and follow the doctor/runtime section, then rerun this script."
        }
        Fail-Verification -Step "doctor" -LikelyCause "Webots runtime readiness is not green." -NextAction $nextAction
    }
} catch {
    Fail-Verification -Step "doctor" `
        -LikelyCause "Webots is missing, WEBOTS_HOME is wrong, or the runtime is not in a supported mode." `
        -NextAction "Run `webots-kit doctor --json` manually and follow $troubleshootingDoc"
}

try {
    $benchmarks = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("benchmark", "list") -StepName "Listing bundled benchmarks"
    $lineFollower = $benchmarks | Where-Object { $_.name -eq "line-follower" } | Select-Object -First 1
    if (-not $lineFollower) {
        Fail-Verification -Step "benchmark list" -LikelyCause "Bundled package assets are missing from the install." -NextAction "Reinstall the package, then rerun this script."
    }
    $worldPath = [string]$lineFollower.world
} catch {
    Fail-Verification -Step "benchmark list" `
        -LikelyCause "The install does not expose the bundled examples correctly." `
        -NextAction "Run `webots-kit benchmark list` manually and confirm `line-follower` exists. If not, reinstall and rerun. See $troubleshootingDoc"
}

try {
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("controller", "scaffold", $controllerPath, "--scenario", "line-follower", "--force") -StepName "Scaffolding a demo controller"
} catch {
    Fail-Verification -Step "controller scaffold" `
        -LikelyCause "The package install is incomplete or the current user cannot write to the temporary workspace." `
        -NextAction "Run `webots-kit controller scaffold `"$controllerPath`" --scenario line-follower --force` manually and inspect the error."
}

try {
    $validation = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("controller", "validate", $controllerPath, "--scenario", "line-follower", "--strict", "--json") -StepName "Validating the demo controller"
    if (-not $validation.valid) {
        Fail-Verification -Step "controller validate" -LikelyCause "The generated scaffold did not validate cleanly in this environment." -NextAction "Run `webots-kit controller validate `"$controllerPath`" --scenario line-follower --strict --json` and inspect $troubleshootingDoc"
    }
} catch {
    Fail-Verification -Step "controller validate" `
        -LikelyCause "The validation runtime or package install is inconsistent." `
        -NextAction "Run the validate command manually and inspect $troubleshootingDoc"
}

try {
    $inspect = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("world", "inspect", $worldPath, "--json") -StepName "Inspecting the bundled line-follower world"
    if ($inspect.status -ne "ready") {
        Fail-Verification -Step "world inspect" -LikelyCause "The bundled world assets are missing or unreadable." -NextAction "Run `webots-kit world inspect `"$worldPath`" --json` manually and inspect the error."
    }
} catch {
    Fail-Verification -Step "world inspect" `
        -LikelyCause "The bundled world asset path is unreadable or the package install is incomplete." `
        -NextAction "Run `webots-kit world inspect `"$worldPath`" --json` manually and inspect $troubleshootingDoc"
}

if ($Runtime) {
    try {
        $benchmark = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("benchmark", "run", "line-follower", "--controller", "example", "--output", $reportPath, "--duration-s", "3") -StepName "Running a real line-follower benchmark"
        if (-not $benchmark.pass) {
            Fail-Verification -Step "benchmark run" -LikelyCause "The runtime started but the benchmark did not pass cleanly." -NextAction "Run `webots-kit benchmark report `"$reportPath`"` and inspect $troubleshootingDoc"
        }
    } catch {
        Fail-Verification -Step "benchmark run" `
            -LikelyCause "The interactive runtime is not actually usable in this shell or machine session." `
            -NextAction "Run `webots-kit benchmark run line-follower --controller example --output `"$reportPath`" --duration-s 3` manually, then inspect $troubleshootingDoc"
    }
}

Write-Host ""
Write-Host "Verification passed."
Write-Host "Workspace: $workspace"
if ($Runtime) {
    Write-Host "Runtime benchmark report: $reportPath"
    Write-Host "Next action: try `webots-kit session start --scenario line-follower --controller example --mode fast --render off`."
} else {
    Write-Host "Next action: rerun this script with -Runtime when you want a full real-benchmark check."
}
