. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
$reportDir = Join-Path $root "workspace\reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$report = Join-Path $reportDir ("BATCH-REPORT-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".md")

$todo = @(Get-ChildItem (Join-Path $root "workspace\tasks\todo") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$inProgress = @(Get-ChildItem (Join-Path $root "workspace\tasks\in_progress") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$done = @(Get-ChildItem (Join-Path $root "workspace\tasks\done") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$review = @(Get-ChildItem (Join-Path $root "workspace\tasks\review") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$failed = @(Get-ChildItem (Join-Path $root "workspace\tasks\failed") -Filter "*.md" -ErrorAction SilentlyContinue).Count
$locks = @(Get-ChildItem (Join-Path $root "workspace\locks") -Filter "*.lock" -ErrorAction SilentlyContinue).Count
$runCount = @(Get-ChildItem (Join-Path $root "workspace\runs") -Filter "*.md" -ErrorAction SilentlyContinue).Count

Set-Content -Path $report -Value "# Batch Review Report`n`nCreated: $(Get-Date)`n`nTodo: $todo`nIn Progress: $inProgress`nReview: $review`nDone: $done`nFailed: $failed`nLocks Remaining: $locks`nRun Logs: $runCount`n`n## Manager Review Notes`n`n- Review dry-run transitions and remaining tasks.`n- Confirm locks were released.`n"
Write-AgentLog "reviewer" "Created batch report $report"
Write-Output $report
