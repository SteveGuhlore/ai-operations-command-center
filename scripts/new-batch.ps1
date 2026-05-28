param(
    [string]$BatchId = "",
    [string]$Project = "sample-project"
)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
if (-not $BatchId) { $BatchId = "BATCH-" + (Get-Date -Format "yyyyMMdd-HHmmss") }

$batchDir = Join-Path $root "workspace\batches"
New-Item -ItemType Directory -Force -Path $batchDir | Out-Null

$todoDir = Join-Path $root "workspace\tasks\todo"
$tasks = Get-ChildItem $todoDir -Filter "*.md" -ErrorAction SilentlyContinue | Sort-Object Name

$manifest = Join-Path $batchDir "$BatchId.md"

$lines = @()
$lines += "# $BatchId"
$lines += ""
$lines += "Project: $Project"
$lines += "Created: $(Get-Date)"
$lines += ""
$lines += "## Tasks"
$lines += ""

foreach ($task in $tasks) { $lines += "- $($task.Name)" }

$lines += ""
$lines += "## Manager Notes"
$lines += ""
$lines += "- Review task ownership before launch."
$lines += "- Dry-run first."
$lines += "- Confirm no forbidden files are touched."
$lines += "- Replace the sample profile before any real worker run."

Set-Content -Path $manifest -Value ($lines -join "`n")
Write-AgentLog "batch" "Created batch manifest $manifest"
Write-Output $manifest
