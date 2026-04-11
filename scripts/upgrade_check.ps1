[CmdletBinding()]
param(
    [switch]$Runtime,
    [switch]$Json,
    [string]$Output,
    [string]$Workspace,
    [ValidateSet("e-puck", "monsterborg-4wd")]
    [string]$RobotProfile = "e-puck"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:StructuredMode = $Json.IsPresent

function Write-Step {
    param([string]$Message)
    if (-not $script:StructuredMode) {
        Write-Host "[upgrade-check] $Message"
    }
}

function Get-CommandTail {
    param([string[]]$CommandParts)

    if ($CommandParts.Length -le 1) {
        return @()
    }
    return $CommandParts[1..($CommandParts.Length - 1)]
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

    throw "Python and webots-kit are not available on PATH."
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

function Emit-Summary {
    param([hashtable]$Summary)

    $jsonText = $Summary | ConvertTo-Json -Depth 10
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

function Fail-UpgradeCheck {
    param(
        [hashtable]$Summary,
        [string]$Step,
        [string]$LikelyCause,
        [string]$NextAction,
        [string]$RawError = ""
    )

    $Summary.status = "failed"
    $Summary.failure = [ordered]@{
        step = $Step
        likely_cause = $LikelyCause
        next_action = $NextAction
        raw_error = $RawError
    }
    $Summary.next_step = $NextAction

    if (-not $script:StructuredMode) {
        Write-Host ""
        Write-Host "Upgrade check failed at: $Step"
        Write-Host "Likely cause: $LikelyCause"
        Write-Host "Next action: $NextAction"
    }

    Emit-Summary -Summary $Summary
    exit 1
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
$verifyScript = Join-Path $PSScriptRoot "verify_install.ps1"
$bootstrapScript = Join-Path $PSScriptRoot "bootstrap_workspace.ps1"
$troubleshootingDoc = Join-Path $repoRoot "docs\troubleshooting.md"

if (-not $Workspace) {
    $Workspace = Join-Path $env:TEMP ("webots-kit-upgrade-" + [System.Guid]::NewGuid().ToString("N"))
}
$workspacePath = if ([System.IO.Path]::IsPathRooted($Workspace)) {
    $Workspace
} else {
    Join-Path (Get-Location).Path $Workspace
}
New-Item -ItemType Directory -Force -Path $workspacePath | Out-Null

$summary = [ordered]@{
    status = "running"
    support_tier = "experimental-foundation"
    robot_profile = $RobotProfile
    workspace = $workspacePath
    runtime_requested = [bool]$Runtime
    checks = [ordered]@{
        verify_install = "pending"
        benchmark_list = "pending"
        bootstrap_line_follower = "pending"
        starter_controller_validate = "pending"
        bootstrap_controller_edit = "pending"
        starter_controller_edit = "pending"
        bootstrap_world_edit = "pending"
        starter_world_validate = "pending"
        starter_world_edit = "pending"
        bootstrap_import_replay = "pending"
        starter_project_import = "pending"
    }
    starter_workspaces = [ordered]@{}
    next_step = $null
    failure = $null
}

try {
    $verifyArgs = @("-ExecutionPolicy", "Bypass", "-File", $verifyScript, "-Json")
    if ($Runtime) {
        $verifyArgs += "-Runtime"
    }
    $verifyArgs += @("-RobotProfile", $RobotProfile)
    $verifyRaw = & powershell @verifyArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($verifyRaw -join [Environment]::NewLine)
    }
    $verifySummary = ($verifyRaw -join [Environment]::NewLine) | ConvertFrom-Json
    $summary.verify_install = $verifySummary
    $summary.checks.verify_install = "passed"
} catch {
    $summary.checks.verify_install = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "verify_install" -LikelyCause "The public install verification path is not green after upgrade." -NextAction "Run powershell -ExecutionPolicy Bypass -File .\\scripts\\verify_install.ps1 -Runtime manually and inspect $troubleshootingDoc" -RawError $_.Exception.Message
}

try {
    $webotsKit = Resolve-WebotsKitCommand
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("benchmark", "list") -StepName "Listing benchmarks after upgrade"
    $summary.checks.benchmark_list = "passed"
} catch {
    $summary.checks.benchmark_list = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "benchmark_list" -LikelyCause "The upgraded package cannot enumerate bundled benchmarks." -NextAction "Run webots-kit benchmark list manually and inspect the install." -RawError $_.Exception.Message
}

try {
    $lineStarter = if ($RobotProfile -eq "monsterborg-4wd") { "monsterborg-line-follower" } else { "line-follower" }
    $lineWorkspaceRaw = & powershell -ExecutionPolicy Bypass -File $bootstrapScript -Starter $lineStarter -Destination (Join-Path $workspacePath "line-follower") -Force -Json
    if ($LASTEXITCODE -ne 0) { throw ($lineWorkspaceRaw -join [Environment]::NewLine) }
    $lineWorkspace = ($lineWorkspaceRaw -join [Environment]::NewLine) | ConvertFrom-Json
    $summary.starter_workspaces.line_follower = $lineWorkspace
    $summary.checks.bootstrap_line_follower = "passed"
} catch {
    $summary.checks.bootstrap_line_follower = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "bootstrap_line_follower" -LikelyCause "The line-follower starter workspace could not be created." -NextAction "Run powershell -ExecutionPolicy Bypass -File .\\scripts\\bootstrap_workspace.ps1 -Starter line-follower manually." -RawError $_.Exception.Message
}

try {
    $controllerPath = Join-Path $summary.starter_workspaces.line_follower.destination "controllers\demo_agent.py"
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("controller", "validate", $controllerPath, "--scenario", "line-follower", "--robot-profile", $RobotProfile, "--strict", "--json") -StepName "Validating starter line-follower controller"
    $summary.checks.starter_controller_validate = "passed"
} catch {
    $summary.checks.starter_controller_validate = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "starter_controller_validate" -LikelyCause "The line-follower starter controller did not validate cleanly." -NextAction "Run the controller validate command shown in the starter README." -RawError $_.Exception.Message
}

try {
    $controllerStarter = if ($RobotProfile -eq "monsterborg-4wd") { "monsterborg-controller-edit" } else { "controller-edit" }
    $controllerEditRaw = & powershell -ExecutionPolicy Bypass -File $bootstrapScript -Starter $controllerStarter -Destination (Join-Path $workspacePath "controller-edit") -Force -Json
    if ($LASTEXITCODE -ne 0) { throw ($controllerEditRaw -join [Environment]::NewLine) }
    $controllerEditWorkspace = ($controllerEditRaw -join [Environment]::NewLine) | ConvertFrom-Json
    $summary.starter_workspaces.controller_edit = $controllerEditWorkspace
    $summary.checks.bootstrap_controller_edit = "passed"
} catch {
    $summary.checks.bootstrap_controller_edit = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "bootstrap_controller_edit" -LikelyCause "The controller-edit starter workspace could not be created." -NextAction "Run powershell -ExecutionPolicy Bypass -File .\\scripts\\bootstrap_workspace.ps1 -Starter controller-edit manually." -RawError $_.Exception.Message
}

try {
    $controllerEditPath = Join-Path $summary.starter_workspaces.controller_edit.destination "controllers\demo_agent.py"
    $controllerEditPlan = Join-Path $summary.starter_workspaces.controller_edit.destination "plans\controller-edit.json"
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("controller", "edit", $controllerEditPath, "--plan", $controllerEditPlan, "--robot-profile", $RobotProfile, "--json") -StepName "Applying starter controller edit plan"
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("controller", "validate", $controllerEditPath, "--scenario", "line-follower", "--robot-profile", $RobotProfile, "--strict", "--json") -StepName "Validating edited starter controller"
    $summary.checks.starter_controller_edit = "passed"
} catch {
    $summary.checks.starter_controller_edit = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "starter_controller_edit" -LikelyCause "The controller-edit starter workspace did not survive inspect/edit/validate." -NextAction "Run the starter controller-edit commands manually." -RawError $_.Exception.Message
}

try {
    $worldStarter = if ($RobotProfile -eq "monsterborg-4wd") { "monsterborg-world-edit" } else { "world-edit" }
    $worldEditRaw = & powershell -ExecutionPolicy Bypass -File $bootstrapScript -Starter $worldStarter -Destination (Join-Path $workspacePath "world-edit") -Force -Json
    if ($LASTEXITCODE -ne 0) { throw ($worldEditRaw -join [Environment]::NewLine) }
    $worldEditWorkspace = ($worldEditRaw -join [Environment]::NewLine) | ConvertFrom-Json
    $summary.starter_workspaces.world_edit = $worldEditWorkspace
    $summary.checks.bootstrap_world_edit = "passed"
} catch {
    $summary.checks.bootstrap_world_edit = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "bootstrap_world_edit" -LikelyCause "The world-edit starter workspace could not be created." -NextAction "Run powershell -ExecutionPolicy Bypass -File .\\scripts\\bootstrap_workspace.ps1 -Starter world-edit manually." -RawError $_.Exception.Message
}

try {
    $worldPath = Join-Path $summary.starter_workspaces.world_edit.destination "worlds\editable_world.wbt"
    $worldPlan = Join-Path $summary.starter_workspaces.world_edit.destination "plans\world-edit.json"
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("world", "validate", $worldPath, "--json") -StepName "Validating starter world before edit"
    $summary.checks.starter_world_validate = "passed"
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("world", "edit", $worldPath, "--plan", $worldPlan, "--json") -StepName "Applying starter world edit plan"
    $null = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("world", "validate", $worldPath, "--json") -StepName "Validating starter world after edit"
    $summary.checks.starter_world_edit = "passed"
} catch {
    if ($summary.checks.starter_world_validate -eq "pending") {
        $summary.checks.starter_world_validate = "failed"
    }
    $summary.checks.starter_world_edit = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "starter_world_edit" -LikelyCause "The world-edit starter workspace did not survive validate/edit/validate." -NextAction "Run the starter world-edit commands manually." -RawError $_.Exception.Message
}

try {
    $importStarter = if ($RobotProfile -eq "monsterborg-4wd") { "monsterborg-import-replay" } else { "import-replay" }
    $importRaw = & powershell -ExecutionPolicy Bypass -File $bootstrapScript -Starter $importStarter -Destination (Join-Path $workspacePath "import-replay") -Force -Json
    if ($LASTEXITCODE -ne 0) { throw ($importRaw -join [Environment]::NewLine) }
    $importWorkspace = ($importRaw -join [Environment]::NewLine) | ConvertFrom-Json
    $summary.starter_workspaces.import_replay = $importWorkspace
    $summary.checks.bootstrap_import_replay = "passed"
} catch {
    $summary.checks.bootstrap_import_replay = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "bootstrap_import_replay" -LikelyCause "The import-replay starter workspace could not be created." -NextAction "Run powershell -ExecutionPolicy Bypass -File .\\scripts\\bootstrap_workspace.ps1 -Starter import-replay manually." -RawError $_.Exception.Message
}

try {
    $importWorld = Join-Path $summary.starter_workspaces.import_replay.destination "worlds\import_world.wbt"
    $importController = Join-Path $summary.starter_workspaces.import_replay.destination "controllers\import_agent.py"
    $importProjectRoot = Join-Path $summary.starter_workspaces.import_replay.destination "imported-project"
    $importSummary = Invoke-WebotsKitJson -Command $webotsKit -Arguments @("project", "import", "--world", $importWorld, "--controller", $importController, "--project-root", $importProjectRoot) -StepName "Importing starter world/controller pair"
    $summary.import_summary = $importSummary
    $summary.checks.starter_project_import = "passed"
} catch {
    $summary.checks.starter_project_import = "failed"
    Fail-UpgradeCheck -Summary $summary -Step "starter_project_import" -LikelyCause "The import-replay starter workspace could not be imported cleanly." -NextAction "Run the starter import command manually." -RawError $_.Exception.Message
}

$summary.status = "ready"
$summary.next_step = if ($Runtime) {
    "Use the starter workspaces in this upgrade-check workspace for team handoff or rerun verify_install.ps1 -Runtime on an interactive machine when you need a real benchmark."
} else {
    "Use the starter workspaces in this upgrade-check workspace or rerun this script with -Runtime for the runtime branch."
}

if (-not $script:StructuredMode) {
    Write-Host ""
    Write-Host "Upgrade check passed."
    Write-Host "Workspace: $workspacePath"
    Write-Host "Next action: $($summary.next_step)"
}

Emit-Summary -Summary $summary
