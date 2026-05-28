. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
Write-Host "AI Agent Command Center Doctor"
Write-Host "Root: $root"
Write-Host ""

$requiredFolders = @(
    "projects",
    "agents",
    "docs",
    "prompts",
    "task_templates",
    "scripts",
    "workspace\tasks\todo",
    "workspace\tasks\in_progress",
    "workspace\tasks\review",
    "workspace\tasks\done",
    "workspace\tasks\failed",
    "workspace\locks",
    "workspace\logs",
    "workspace\reports",
    "workspace\runs",
    "workspace\context"
)

$missing = @()
foreach ($folder in $requiredFolders) {
    $path = Join-Path $root $folder
    if (-not (Test-Path $path)) { $missing += $folder }
}

$requiredScripts = @(
    "scripts\status.ps1",
    "scripts\launch-batch.ps1",
    "scripts\auto-agent.ps1",
    "scripts\pick-task.ps1",
    "scripts\move-task.ps1",
    "scripts\release-lock.ps1",
    "scripts\clean-expired-locks.ps1",
    "scripts\reset-sample-tasks.ps1",
    "scripts\validate-agents.ps1",
    "scripts\validate-tools.ps1",
    "scripts\validate-guardrails.ps1",
    "scripts\validate-budgets.ps1",
    "scripts\validate-revenue-pods.ps1",
    "scripts\validate-project.ps1",
    "scripts\validate-tasks.ps1",
    "scripts\safe-launch.ps1"
)

$requiredConfigFiles = @(
    "config\agents.example.yaml",
    "config\tools.example.yaml",
    "config\guardrails.example.yaml",
    "config\budgets.example.yaml",
    "config\schedules.example.yaml",
    "config\revenue-pods.example.yaml"
)

$missingScripts = @()
foreach ($script in $requiredScripts) {
    $path = Join-Path $root $script
    if (-not (Test-Path $path)) { $missingScripts += $script }
}

$missingConfigFiles = @()
foreach ($configFile in $requiredConfigFiles) {
    $path = Join-Path $root $configFile
    if (-not (Test-Path $path)) { $missingConfigFiles += $configFile }
}

$todoCount = @(Get-ChildItem (Join-Path $root "workspace\tasks\todo") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$inProgressCount = @(Get-ChildItem (Join-Path $root "workspace\tasks\in_progress") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$reviewCount = @(Get-ChildItem (Join-Path $root "workspace\tasks\review") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$doneCount = @(Get-ChildItem (Join-Path $root "workspace\tasks\done") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$failedCount = @(Get-ChildItem (Join-Path $root "workspace\tasks\failed") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$totalTaskCount = $todoCount + $inProgressCount + $reviewCount + $doneCount + $failedCount
$lockCount = @(Get-ChildItem (Join-Path $root "workspace\locks") -Filter "*.lock" -ErrorAction SilentlyContinue).Count
$profilePath = Join-Path $root "projects\sample-project.yaml"

Write-Host "Todo tasks: $todoCount"
Write-Host "In-progress tasks: $inProgressCount"
Write-Host "Review tasks: $reviewCount"
Write-Host "Done tasks: $doneCount"
Write-Host "Failed tasks: $failedCount"
Write-Host "Total tasks: $totalTaskCount"
Write-Host "Remaining locks: $lockCount"
Write-Host "Sample project profile exists: $(Test-Path $profilePath)"
Write-Host "Config files present: $($requiredConfigFiles.Count - $missingConfigFiles.Count)/$($requiredConfigFiles.Count)"
Write-Host ""

if (
    $missing.Count -eq 0 -and
    $missingScripts.Count -eq 0 -and
    $missingConfigFiles.Count -eq 0 -and
    $totalTaskCount -gt 0 -and
    $inProgressCount -eq 0 -and
    $lockCount -eq 0 -and
    (Test-Path $profilePath)
) {
    Write-Host "Doctor result: PASS"
    exit 0
}

Write-Host "Doctor result: NEEDS ATTENTION"
if ($missing.Count -gt 0) {
    Write-Host "Missing folders:"
    $missing | ForEach-Object { Write-Host " - $_" }
}
if ($missingScripts.Count -gt 0) {
    Write-Host "Missing scripts:"
    $missingScripts | ForEach-Object { Write-Host " - $_" }
}
if ($missingConfigFiles.Count -gt 0) {
    Write-Host "Missing config files:"
    $missingConfigFiles | ForEach-Object { Write-Host " - $_" }
}
if ($totalTaskCount -le 0) {
    Write-Host "Task issue:"
    Write-Host " - No tasks found across todo, in_progress, review, done, or failed."
}
if ($inProgressCount -gt 0) {
    Write-Host "Task issue:"
    Write-Host " - One or more tasks are still in workspace\tasks\in_progress."
}
if ($lockCount -gt 0) {
    Write-Host "Lock issue:"
    Write-Host " - One or more lock files remain in workspace\locks."
}
exit 1
