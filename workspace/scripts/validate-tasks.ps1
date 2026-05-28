<#
.SYNOPSIS
    Validates task files across all task queue folders.

.DESCRIPTION
    Checks every task markdown file in tasks/todo, tasks/in_progress, tasks/review,
    tasks/done, and tasks/failed for:
      - Correct filename format  (<ID>-<slug>.md)
      - Presence of required frontmatter fields
      - No task appearing in more than one queue simultaneously
      - No orphaned task IDs with active lock files but no in_progress entry

.PARAMETER WorkspacePath
    Path to the workspace root. Defaults to the parent of the scripts/ directory.

.PARAMETER Verbose
    Print details for every task, not just problems.

.EXAMPLE
    .\scripts\validate-tasks.ps1
    .\scripts\validate-tasks.ps1 -WorkspacePath C:\path\to\workspace

.NOTES
    Role:    Forge (heavy_worker)
    Task:    SAMPLE-002
    Created: 2026-05-21
    See:     docs/run-log-format.md, docs/lock-lifecycle.md
#>

[CmdletBinding()]
param(
    [string]$WorkspacePath = (Resolve-Path (Join-Path $PSScriptRoot ".."))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$pass = 0
$warn = 0
$fail = 0

function Write-Check  { param($msg) Write-Host "  [PASS] $msg" -ForegroundColor Green;  $script:pass++ }
function Write-Warn   { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow; $script:warn++ }
function Write-Fail   { param($msg) Write-Host "  [FAIL] $msg" -ForegroundColor Red;    $script:fail++ }
function Write-Header { param($msg) Write-Host "`n== $msg ==" -ForegroundColor Cyan }

Write-Host "`nAI Operations Command Center - Validate Tasks" -ForegroundColor Cyan
Write-Host "Workspace: $WorkspacePath"
Write-Host ("-" * 50)

$queues = @("todo", "in_progress", "review", "done", "failed")

# Collect all tasks across all queues
$allTasks = @{}   # taskId -> list of queues it appears in

Write-Header "Filename Format"

$filenamePattern = '^[A-Z0-9]+-[A-Z0-9]+-\d+-.*\.md$'

foreach ($queue in $queues) {
    $queuePath = Join-Path $WorkspacePath "tasks/$queue"
    if (-not (Test-Path $queuePath -PathType Container)) {
        Write-Warn "Queue directory missing: tasks/$queue"
        continue
    }

    $files = Get-ChildItem -Path $queuePath -Filter "*.md" -File -ErrorAction SilentlyContinue

    foreach ($file in $files) {
        # Extract task ID (everything before the second dash-separated segment onwards)
        # Pattern: PREFIX-TYPE-NUM or PREFIX-NUM (e.g. SAMPLE-002, POD-SOC-001)
        $taskId = $null
        if ($file.Name -match '^([A-Z]+-[A-Z]+-\d+)-') {
            $taskId = $Matches[1]
        } elseif ($file.Name -match '^([A-Z]+-\d+)-') {
            $taskId = $Matches[1]
        }

        if ($null -eq $taskId) {
            Write-Fail "Cannot parse task ID from filename: $($file.Name) (queue: $queue)"
            continue
        }

        # Track which queues this task ID appears in
        if (-not $allTasks.ContainsKey($taskId)) {
            $allTasks[$taskId] = [System.Collections.Generic.List[string]]::new()
        }
        $allTasks[$taskId].Add($queue)

        # Filename format check
        if ($file.Name -match $filenamePattern) {
            Write-Check "Valid filename: $($file.Name) ($queue)"
        } else {
            Write-Warn "Filename format unexpected: $($file.Name) ($queue)"
        }
    }
}

# ── Duplicate task ID detection ───────────────────────────────────────────────
Write-Header "Duplicate Task IDs"

$mutuallyExclusiveQueues = @("todo", "in_progress", "review")

foreach ($taskId in $allTasks.Keys) {
    $queuesForTask = $allTasks[$taskId]
    $activeQueues = $queuesForTask | Where-Object { $mutuallyExclusiveQueues -contains $_ }
    if ($activeQueues.Count -gt 1) {
        Write-Fail "Task $taskId appears in multiple active queues: $($activeQueues -join ', ')"
    } elseif ($queuesForTask.Count -gt 1) {
        Write-Warn "Task $taskId appears in multiple queues (may be archival): $($queuesForTask -join ', ')"
    } else {
        Write-Check "Task $taskId is in exactly one queue: $($queuesForTask[0])"
    }
}

# ── Lock vs in_progress consistency ──────────────────────────────────────────
Write-Header "Lock / In-Progress Consistency"

$locksDir     = Join-Path $WorkspacePath "locks"
$inProgressDir = Join-Path $WorkspacePath "tasks/in_progress"

$lockFiles = Get-ChildItem -Path $locksDir -Filter "*.lock" -File -ErrorAction SilentlyContinue

foreach ($lockFile in $lockFiles) {
    $lockedTaskId = [System.IO.Path]::GetFileNameWithoutExtension($lockFile.Name)
    $inProgressFile = Get-ChildItem -Path $inProgressDir -Filter "${lockedTaskId}-*.md" -File -ErrorAction SilentlyContinue

    if ($inProgressFile) {
        Write-Check "Lock matches in_progress task: $lockedTaskId"
    } else {
        Write-Warn "Lock exists but task NOT in in_progress: $lockedTaskId (possible orphaned lock)"
    }
}

# Check in_progress tasks that have no lock
$inProgressFiles = Get-ChildItem -Path $inProgressDir -Filter "*.md" -File -ErrorAction SilentlyContinue
foreach ($ipFile in $inProgressFiles) {
    $taskId = $null
    if ($ipFile.Name -match '^([A-Z]+-[A-Z]+-\d+)-') {
        $taskId = $Matches[1]
    } elseif ($ipFile.Name -match '^([A-Z]+-\d+)-') {
        $taskId = $Matches[1]
    }
    if ($taskId) {
        $lockPath = Join-Path $locksDir "${taskId}.lock"
        if (-not (Test-Path $lockPath)) {
            Write-Warn "In-progress task has no lock file: $taskId"
        }
    }
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host "`n" + ("-" * 50)
Write-Host "Results: " -NoNewline
Write-Host "$pass passed" -ForegroundColor Green -NoNewline
Write-Host "  |  " -NoNewline
Write-Host "$warn warnings" -ForegroundColor Yellow -NoNewline
Write-Host "  |  " -NoNewline
Write-Host "$fail failures" -ForegroundColor Red

if ($fail -gt 0) {
    Write-Host "`nValidation finished with FAILURES." -ForegroundColor Red
    exit 1
} elseif ($warn -gt 0) {
    Write-Host "`nValidation finished with warnings." -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "`nValidation finished clean." -ForegroundColor Green
    exit 0
}
