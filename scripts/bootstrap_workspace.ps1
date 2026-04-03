[CmdletBinding()]
param(
    [string]$Starter = "line-follower",
    [string]$Destination,
    [switch]$Force,
    [switch]$Json
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
    param([string]$Message)
    if (-not $Json) {
        Write-Host "[bootstrap] $Message"
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$starterRoot = Join-Path $repoRoot "examples\getting-started\$Starter"
if (-not (Test-Path -LiteralPath $starterRoot)) {
    throw "Unknown starter workspace '$Starter'."
}

$metadataPath = Join-Path $starterRoot "starter.json"
if (-not (Test-Path -LiteralPath $metadataPath)) {
    throw "Starter metadata is missing: $metadataPath"
}
$metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json

if (-not $Destination) {
    $Destination = Join-Path (Get-Location).Path $Starter
}
$destinationPath = if ([System.IO.Path]::IsPathRooted($Destination)) {
    $Destination
} else {
    Join-Path (Get-Location).Path $Destination
}

if (Test-Path -LiteralPath $destinationPath) {
    if (-not $Force) {
        throw "Destination already exists. Use -Force to overwrite: $destinationPath"
    }
    Remove-Item -LiteralPath $destinationPath -Recurse -Force
}

Write-Step "Copying starter workspace '$Starter'"
New-Item -ItemType Directory -Force -Path $destinationPath | Out-Null
Get-ChildItem -LiteralPath $starterRoot -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $destinationPath -Recurse -Force
}

$payload = [ordered]@{
    starter = $metadata.name
    title = $metadata.title
    flow = $metadata.flow
    support_tier = $metadata.support_tier
    source = $starterRoot
    destination = $destinationPath
    readme_path = Join-Path $destinationPath "README.md"
    expected_green = $metadata.expected_green
    recommended_commands = @($metadata.recommended_commands)
}

if ($Json) {
    $payload | ConvertTo-Json -Depth 10
    exit 0
}

Write-Host "Starter workspace ready."
Write-Host "Starter: $($payload.starter)"
Write-Host "Destination: $($payload.destination)"
Write-Host "Expected green: $($payload.expected_green)"
Write-Host "Readme: $($payload.readme_path)"
Write-Host "Recommended commands:"
foreach ($command in $payload.recommended_commands) {
    Write-Host "  $command"
}
