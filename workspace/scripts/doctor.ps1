<#
.SYNOPSIS
    Doctor script for the AI Operations Command Center workspace.

.DESCRIPTION
    Runs a series of health checks on the local workspace:
      - Verifies required directories exist
      - Checks for orphaned lock files
      - Validates run log field completeness
      - Reports stale locks (older than 24 hours)
      - Optionally removes orphaned locks with -Fix

.PARAMETER Fix
    When set, automatically removes orphaned lock files after confirming with the user.

.PARAMETER WorkspacePath
    Path to the workspace root. Defaults to the parent of the scripts/ directory.

.EXAMPLE
    .\scripts\doctor.ps1
    .\scripts\doctor.ps1 -Fix

.NOTES
    Role:    Forge (heavy_worker)
    Task:    SAMPLE-002
    Created: 2026-05-21
    See:     docs/lock-lifecycle.md, docs/run-log-format.md
#>

[CmdletBinding()]
param(
    [switch]$Fix,
    [string]$WorkspacePath = (Resolve-Path (Join-Path $PSScriptRoot ".."))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$pass  = 0
$warn  = 0
$fail  = 0

function Write-Check  { param($msg) Write-Host "  [PASS] $msg" -ForegroundColor Green;  $script:pass++ }
function Write-Warn   { param($msg) Write-Host "  [WARN] $msg" -ForegroundColor Yellow; $script:warn++ }
function Write-Fail   { param($msg) Write-Host "  [FAIL] $msg" -ForegroundColor Red;    $script:fail++ }
function Write-Header { param($msg) Write-Host "`n== $msg ==" -ForegroundColor Cyan }

Write-Host "`nAI Operations Command Center - Doctor" -ForegroundColor Cyan
Write-Host "Workspace: $WorkspacePath"
Write-Host ("-" * 50)

# ── 1. Required directories ───────────────────────────────────────────────────
Write-Header "Directory Structure"

$requiredDirs = @(
    "tasks/todo", "tasks/in_progress", "tasks/review", "tasks/done", "tasks/failed",
    "locks", "runs", "logs", "reports", "docs", "scripts", "outputs", "assets"
)

foreach ($dir in $requiredDirs) {
    $fullPath = Join-Path $WorkspacePath $dir
    if (Test-Path $fullPath -PathType Container) {
        Write-Check "Directory exists: $dir"
    } else {
        Write-Fail "Missing directory: $dir"
    }
}

# ── 2. Required files ─────────────────────────────────────────────────────────
Write-Header "Required Files"

$requiredFiles = @(
    "dashboard-state.json",
    "ledger/daily-spend.json",
    "logs/agent-command-center.log",
    "docs/run-log-format.md",
    "docs/batch-report-format.md",
    "docs/lock-lifecycle.md"
)

foreach ($file in $requiredFiles) {
    $fullPath = Join-Path $WorkspacePath $file
    if (Test-Path $fullPath -PathType Leaf) {
        Write-Check "File exists: $file"
    } else {
        Write-Warn "Missing file: $file"
    }
}

# ── 3. Orphaned lock detection ────────────────────────────────────────────────
Write-Header "Lock Files"

$locksDir = Join-Path $WorkspacePath "locks"
$runsDir  = Join-Path $WorkspacePath "runs"
$lockFiles = Get-ChildItem -Path $locksDir -Filter "*.lock" -File -ErrorAction SilentlyContinue

if ($lockFiles.Count -eq 0) {
    Write-Check "No lock files present."
} else {
    foreach ($lockFile in $lockFiles) {
        $taskId = [System.IO.Path]::GetFileNameWithoutExtension($lockFile.Name)

        # Check age
        $ageHours = ((Get-Date) - $lockFile.LastWriteTime).TotalHours
        if ($ageHours -gt 24) {
            Write-Warn "Stale lock (${ageHours:F1}h old): $($lockFile.Name)"
        }

        # Find matching run log
        $matchingLogs = Get-ChildItem -Path $runsDir -Filter "${taskId}-*.md" -File -ErrorAction SilentlyContinue
        if ($matchingLogs.Count -eq 0) {
            Write-Warn "Unknown lock - no run log found for: $($lockFile.Name)"
        } else {
            # Check if any run log says lock was released
            foreach ($log in $matchingLogs) {
                $content = Get-Content $log.FullName -Raw
                if ($content -match "Lock released:\s*yes") {
                    Write-Warn "Orphaned lock - run log says released but lock file exists: $($lockFile.Name)"
                    if ($Fix) {
                        $answer = Read-Host "  Remove $($lockFile.Name)? [y/N]"
                        if ($answer -ieq "y") {
                            Remove-Item $lockFile.FullName -Force
                            Write-Host "  Removed: $($lockFile.Name)" -ForegroundColor Yellow
                        }
                    }
                } elseif ($content -match "Lock released:\s*no") {
                    Write-Warn "Lock NOT released per run log: $($lockFile.Name)"
                }
            }
        }
    }
}

# ── 4. Run log field completeness ─────────────────────────────────────────────
Write-Header "Run Log Completeness"

$requiredLogFields = @(
    "Source task filename",
    "Task id",
    "Assigned worker type",
    "Assigned worker display name",
    "Worker name",
    "Started",
    "Starting status",
    "Ending status",
    "Lock created",
    "Lock released"
)

$runLogs = Get-ChildItem -Path $runsDir -Filter "*.md" -File -ErrorAction SilentlyContinue

if ($runLogs.Count -eq 0) {
    Write-Warn "No run logs found in runs/"
} else {
    foreach ($log in $runLogs) {
        $content = Get-Content $log.FullName -Raw
        $missing = @()
        foreach ($field in $requiredLogFields) {
            if ($content -notmatch "${field}:") {
                $missing += $field
            }
        }
        if ($missing.Count -eq 0) {
            Write-Check "Run log complete: $($log.Name)"
        } else {
            Write-Warn "Run log '$($log.Name)' missing fields: $($missing -join ', ')"
        }
    }
}

# ── 5. Summary ────────────────────────────────────────────────────────────────
Write-Host "`n" + ("-" * 50)
Write-Host "Results: " -NoNewline
Write-Host "$pass passed" -ForegroundColor Green -NoNewline
Write-Host "  |  " -NoNewline
Write-Host "$warn warnings" -ForegroundColor Yellow -NoNewline
Write-Host "  |  " -NoNewline
Write-Host "$fail failures" -ForegroundColor Red

if ($fail -gt 0) {
    Write-Host "`nDoctor finished with FAILURES." -ForegroundColor Red
    exit 1
} elseif ($warn -gt 0) {
    Write-Host "`nDoctor finished with warnings." -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "`nDoctor finished clean." -ForegroundColor Green
    exit 0
}
