[CmdletBinding()]
param(
    [switch]$Runtime,
    [switch]$Json,
    [string]$Output,
    [ValidateSet("e-puck", "monsterborg-4wd")]
    [string]$RobotProfile = "e-puck"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:StructuredMode = $Json.IsPresent
$script:Summary = [ordered]@{
    status = "running"
    support_tier = "stable"
    version = $null
    robot_profile = $RobotProfile
    workspace = $null
    report_path = $null
    runtime_requested = [bool]$Runtime
    runtime_benchmark_skipped = $false
    runtime_benchmark_passed = $null
    checks = [ordered]@{
        version = "pending"
        doctor = "pending"
        benchmark_list = "pending"
        controller_scaffold = "pending"
        controller_validate = "pending"
        world_inspect = "pending"
        runtime_benchmark = if ($Runtime) { "pending" } else { "not-requested" }
    }
    next_step = $null
    failure = $null
}

function Write-Step {
    param([string]$Message)
    if (-not $script:StructuredMode) {
        Write-Host "[verify] $Message"
    }
}

function Get-CommandTail {
    param([string[]]$CommandParts)

    if ($CommandParts.Length -le 1) {
        return @()
    }
    return $CommandParts[1..($CommandParts.Length - 1)]
}

function Test-GitHubHostedRunner {
    return $env:GITHUB_ACTIONS -eq "true" -and $env:RUNNER_ENVIRONMENT -eq "github-hosted"
}

function Set-CheckState {
    param(
        [string]$Name,
        [string]$State
    )

    $script:Summary.checks[$Name] = $State
}

function Emit-Summary {
    $jsonText = $script:Summary | ConvertTo-Json -Depth 10

    if ($Output) {
        $outputPath = if ([System.IO.Path]::IsPathRooted($Output)) {
            $Output
        } else {
            Join-Path (Get-Location).Path $Output
        }
        $outputDir = Split-Path -Parent $outputPath
        if ($outputDir) {
            New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
        }
        Set-Content -LiteralPath $outputPath -Value $jsonText -Encoding utf8
    }

    if ($script:StructuredMode) {
        Write-Output $jsonText
    }
}

function Fail-Verification {
    param(
        [string]$Step,
        [string]$LikelyCause,
        [string]$NextAction,
        [string]$RawError = ""
    )

    $script:Summary.status = "failed"
    $script:Summary.failure = [ordered]@{
        step = $Step
        likely_cause = $LikelyCause
        next_action = $NextAction
        raw_error = $RawError
    }
    $script:Summary.next_step = $NextAction

    if (-not $script:StructuredMode) {
        Write-Host ""
        Write-Host "Verification failed at: $Step"
        Write-Host "Likely cause: $LikelyCause"
        Write-Host "Next action: $NextAction"
    }

    Emit-Summary
    exit 1
}

function Resolve-PythonCommand {
    if ($env:WEBOTS_KIT_PYTHON) {
        $explicitPython = $env:WEBOTS_KIT_PYTHON.Trim()
        if ($explicitPython -and (Test-Path -LiteralPath $explicitPython)) {
            return ,@($explicitPython)
        }
    }

    if ($env:pythonLocation) {
        $actionsPython = Join-Path $env:pythonLocation "python.exe"
        if (Test-Path -LiteralPath $actionsPython) {
            return ,@($actionsPython)
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return ,@($pythonCommand.Source)
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return ,@($pyLauncher.Source, "-3")
    }

    throw "Python was not found on PATH."
}

function Get-WebotsKitCommandCandidates {
    param([string[]]$PythonCommand)

    $candidates = [System.Collections.Generic.List[string]]::new()

    $resolvedPython = $PythonCommand[0]
    if ($resolvedPython) {
        $pythonDir = Split-Path -Parent $resolvedPython
        foreach ($relative in @("webots-kit.exe", "webots-kit", "Scripts\webots-kit.exe", "Scripts\webots-kit", "..\Scripts\webots-kit.exe", "..\Scripts\webots-kit")) {
            $candidate = [System.IO.Path]::GetFullPath((Join-Path $pythonDir $relative))
            if ((Test-Path -LiteralPath $candidate) -and -not $candidates.Contains($candidate)) {
                [void]$candidates.Add($candidate)
            }
        }
    }

    foreach ($binDir in @($env:PIPX_BIN_DIR, (Join-Path $HOME ".local\bin"), (Join-Path $HOME ".local\Bin"))) {
        if (-not $binDir) {
            continue
        }
        foreach ($leaf in @("webots-kit.exe", "webots-kit")) {
            $candidate = Join-Path $binDir $leaf
            if ((Test-Path -LiteralPath $candidate) -and -not $candidates.Contains($candidate)) {
                [void]$candidates.Add($candidate)
            }
        }
    }

    try {
        $pipxBinDir = & $resolvedPython @(Get-CommandTail -CommandParts $PythonCommand) -m pipx environment --value PIPX_BIN_DIR 2>$null
        if ($LASTEXITCODE -eq 0) {
            $pipxBin = (($pipxBinDir | Where-Object { $_ -and $_.Trim() }) | Select-Object -Last 1).Trim()
            if ($pipxBin) {
                foreach ($leaf in @("webots-kit.exe", "webots-kit")) {
                    $candidate = Join-Path $pipxBin $leaf
                    if ((Test-Path -LiteralPath $candidate) -and -not $candidates.Contains($candidate)) {
                        [void]$candidates.Add($candidate)
                    }
                }
            }
        }
    } catch {
    }

    return $candidates
}

function Resolve-WebotsKitCommand {
    $preferModuleEntrypoint = [bool]($env:WEBOTS_KIT_PYTHON -or $env:pythonLocation)

    if ($preferModuleEntrypoint) {
        $pythonCommand = @(Resolve-PythonCommand)
        & $pythonCommand[0] @(Get-CommandTail -CommandParts $pythonCommand) -m webots_mcp_kit.cli --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return ,@($pythonCommand + @("-m", "webots_mcp_kit.cli"))
        }
    }

    $command = Get-Command webots-kit -ErrorAction SilentlyContinue
    if ($command) {
        return ,@($command.Source)
    }

    $pythonCommand = @(Resolve-PythonCommand)
    foreach ($candidate in Get-WebotsKitCommandCandidates -PythonCommand $pythonCommand) {
        return ,@($candidate)
    }

    & $pythonCommand[0] @(Get-CommandTail -CommandParts $pythonCommand) -m webots_mcp_kit.cli --version *> $null
    if ($LASTEXITCODE -eq 0) {
        return ,@($pythonCommand + @("-m", "webots_mcp_kit.cli"))
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
$runtimeBenchmarkSkipped = $false
$script:Summary.workspace = $workspace
$script:Summary.report_path = $reportPath

try {
    $webotsKit = Resolve-WebotsKitCommand
} catch {
    Set-CheckState -Name "version" -State "failed"
    Fail-Verification -Step "command resolution" `
        -LikelyCause "The package is installed but the current shell cannot see the `webots-kit` command yet." `
        -NextAction "Start a new PowerShell window, then rerun this script. If you installed with pipx, run `python -m pipx ensurepath` first. See $troubleshootingDoc" `
        -RawError $_.Exception.Message
}

try {
    $versionText = Invoke-WebotsKitText -Command $webotsKit -Arguments @("--version") -StepName "Checking webots-kit version"
    $script:Summary.version = $versionText.Trim()
    Set-CheckState -Name "version" -State "passed"
    if (-not $script:StructuredMode) {
        Write-Host $versionText
    }
} catch {
    Set-CheckState -Name "version" -State "failed"
    Fail-Verification -Step "version check" `
        -LikelyCause "The installed package is incomplete or the shell resolved the wrong `webots-kit` command." `
        -NextAction "Reinstall with `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Upgrade`, then rerun this script. See $troubleshootingDoc" `
        -RawError $_.Exception.Message
}

try {
    $doctor = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("doctor", "--json") -StepName "Running doctor"
    if ($doctor.status -ne "ready") {
        Set-CheckState -Name "doctor" -State "failed"
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
    Set-CheckState -Name "doctor" -State "passed"
} catch {
    Set-CheckState -Name "doctor" -State "failed"
    Fail-Verification -Step "doctor" `
        -LikelyCause "Webots is missing, WEBOTS_HOME is wrong, or the runtime is not in a supported mode." `
        -NextAction "Run `webots-kit doctor --json` manually and follow $troubleshootingDoc" `
        -RawError $_.Exception.Message
}

try {
    $benchmarks = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("benchmark", "list") -StepName "Listing bundled benchmarks"
    $lineFollower = $benchmarks | Where-Object { $_.name -eq "line-follower" -and $_.robot_profile -eq $RobotProfile } | Select-Object -First 1
    if (-not $lineFollower) {
        Set-CheckState -Name "benchmark_list" -State "failed"
        Fail-Verification -Step "benchmark list" -LikelyCause "Bundled package assets for the selected robot profile are missing from the install." -NextAction "Reinstall the package, then rerun this script."
    }
    $worldPath = [string]$lineFollower.world
    Set-CheckState -Name "benchmark_list" -State "passed"
} catch {
    Set-CheckState -Name "benchmark_list" -State "failed"
    Fail-Verification -Step "benchmark list" `
        -LikelyCause "The install does not expose the bundled examples correctly." `
        -NextAction "Run `webots-kit benchmark list` manually and confirm `line-follower` exists. If not, reinstall and rerun. See $troubleshootingDoc" `
        -RawError $_.Exception.Message
}

try {
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("controller", "scaffold", $controllerPath, "--scenario", "line-follower", "--robot-profile", $RobotProfile, "--force") -StepName "Scaffolding a demo controller"
    Set-CheckState -Name "controller_scaffold" -State "passed"
} catch {
    Set-CheckState -Name "controller_scaffold" -State "failed"
    Fail-Verification -Step "controller scaffold" `
        -LikelyCause "The package install is incomplete or the current user cannot write to the temporary workspace." `
        -NextAction "Run `webots-kit controller scaffold `"$controllerPath`" --scenario line-follower --robot-profile $RobotProfile --force` manually and inspect the error." `
        -RawError $_.Exception.Message
}

try {
    $validation = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("controller", "validate", $controllerPath, "--scenario", "line-follower", "--robot-profile", $RobotProfile, "--strict", "--json") -StepName "Validating the demo controller"
    if (-not $validation.valid) {
        Set-CheckState -Name "controller_validate" -State "failed"
        Fail-Verification -Step "controller validate" -LikelyCause "The generated scaffold did not validate cleanly in this environment." -NextAction "Run `webots-kit controller validate `"$controllerPath`" --scenario line-follower --robot-profile $RobotProfile --strict --json` and inspect $troubleshootingDoc"
    }
    Set-CheckState -Name "controller_validate" -State "passed"
} catch {
    Set-CheckState -Name "controller_validate" -State "failed"
    Fail-Verification -Step "controller validate" `
        -LikelyCause "The validation runtime or package install is inconsistent." `
        -NextAction "Run the validate command manually and inspect $troubleshootingDoc" `
        -RawError $_.Exception.Message
}

try {
    $inspect = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("world", "inspect", $worldPath, "--json") -StepName "Inspecting the bundled line-follower world"
    if ($inspect.status -ne "ready") {
        Set-CheckState -Name "world_inspect" -State "failed"
        Fail-Verification -Step "world inspect" -LikelyCause "The bundled world assets are missing or unreadable." -NextAction "Run `webots-kit world inspect `"$worldPath`" --json` manually and inspect the error."
    }
    Set-CheckState -Name "world_inspect" -State "passed"
} catch {
    Set-CheckState -Name "world_inspect" -State "failed"
    Fail-Verification -Step "world inspect" `
        -LikelyCause "The bundled world asset path is unreadable or the package install is incomplete." `
        -NextAction "Run `webots-kit world inspect `"$worldPath`" --json` manually and inspect $troubleshootingDoc" `
        -RawError $_.Exception.Message
}

if ($Runtime) {
    if (Test-GitHubHostedRunner) {
        $runtimeBenchmarkSkipped = $true
        $script:Summary.runtime_benchmark_skipped = $true
        Set-CheckState -Name "runtime_benchmark" -State "skipped"
        Write-Step "Skipping real runtime benchmark on the GitHub-hosted runner"
        if (-not $script:StructuredMode) {
            Write-Host "Runtime benchmark skipped: GitHub-hosted Windows runners are not a supported interactive Webots runtime."
            Write-Host "Quick install verification still passed."
        }
    } else {
        try {
            $benchmark = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("benchmark", "run", "line-follower", "--controller", "example", "--robot-profile", $RobotProfile, "--output", $reportPath, "--duration-s", "3") -StepName "Running a real line-follower benchmark"
            if (-not $benchmark.pass) {
                Set-CheckState -Name "runtime_benchmark" -State "failed"
                $script:Summary.runtime_benchmark_passed = $false
                Fail-Verification -Step "benchmark run" -LikelyCause "The runtime started but the benchmark did not pass cleanly." -NextAction "Run `webots-kit benchmark report `"$reportPath`"` and inspect $troubleshootingDoc"
            }
            Set-CheckState -Name "runtime_benchmark" -State "passed"
            $script:Summary.runtime_benchmark_passed = $true
        } catch {
            Set-CheckState -Name "runtime_benchmark" -State "failed"
            $script:Summary.runtime_benchmark_passed = $false
            Fail-Verification -Step "benchmark run" `
                -LikelyCause "The interactive runtime is not actually usable in this shell or machine session." `
                -NextAction "Run `webots-kit benchmark run line-follower --controller example --robot-profile $RobotProfile --output `"$reportPath`" --duration-s 3` manually, then inspect $troubleshootingDoc" `
                -RawError $_.Exception.Message
        }
    }
}

$script:Summary.status = "ready"
if ($Runtime) {
    if ($runtimeBenchmarkSkipped) {
        $script:Summary.next_step = "Rerun this script with -Runtime on a local Windows machine or self-hosted interactive-webots runner when you need a real benchmark."
    } else {
        $script:Summary.next_step = "Try `webots-kit session start --scenario line-follower --controller example --robot-profile $RobotProfile --mode fast --render off`."
    }
} else {
    $script:Summary.next_step = "Rerun this script with -Runtime when you want a full real-benchmark check."
}

if (-not $script:StructuredMode) {
    Write-Host ""
    Write-Host "Verification passed."
    Write-Host "Workspace: $workspace"
    if ($Runtime) {
        if ($runtimeBenchmarkSkipped) {
            Write-Host "Next action: $($script:Summary.next_step)"
        } else {
            Write-Host "Runtime benchmark report: $reportPath"
            Write-Host "Next action: $($script:Summary.next_step)"
        }
    } else {
        Write-Host "Next action: $($script:Summary.next_step)"
    }
}

Emit-Summary
