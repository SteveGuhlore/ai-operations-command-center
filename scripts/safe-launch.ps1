param(
    [int]$HeavyWorkers = 1,
    [int]$DebugWorkers = 1,
    [switch]$DryRun,
    [switch]$AllowRealRun
)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

function Get-TaskStatusCounts {
    $root = Get-CommandCenterRoot
    $statuses = "todo","in_progress","review","done","failed"
    $counts = [ordered]@{}

    foreach ($status in $statuses) {
        $dir = Join-Path $root "workspace\tasks\$status"
        $counts[$status] = @(Get-ChildItem $dir -Filter "*.md" -ErrorAction SilentlyContinue).Count
    }

    return $counts
}

Write-AgentLog "safe-launch" "Preflight started. DryRun=$DryRun AllowRealRun=$AllowRealRun"

& "$PSScriptRoot\doctor.ps1"
if ($LASTEXITCODE -ne 0) { throw "Doctor check failed. Fix command center before launch." }

& "$PSScriptRoot\validate-project.ps1" -AllowPlaceholderPath:$DryRun
if ($LASTEXITCODE -ne 0) { throw "Project profile validation failed." }

& "$PSScriptRoot\validate-tasks.ps1"
if ($LASTEXITCODE -ne 0) { throw "Task validation failed." }

if (-not $DryRun -and -not $AllowRealRun) {
    throw "Blocked real launch. Use -DryRun for safe simulation, or pass -AllowRealRun only when you intentionally want background worker jobs."
}

if ($DryRun) {
    Write-Host "Safe-launch is running in dry-run mode."
    Write-Host "Display names: manager=Atlas, heavy_worker=Forge, debug_worker=Scout."
    Write-Host "This will simulate task locking and status movement without starting background workers or calling any external APIs."
} else {
    Write-Host "Warning: real launch will start background worker jobs."
    Write-Host "Only continue in trusted, reviewed environments."
}

& "$PSScriptRoot\launch-batch.ps1" -HeavyWorkers $HeavyWorkers -DebugWorkers $DebugWorkers -DryRun:$DryRun

if ($DryRun) {
    $reportPath = & "$PSScriptRoot\review-batch.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Dry-run report generation failed." }

    $remainingLocks = @(Get-ChildItem (Join-Path (Get-CommandCenterRoot) "workspace\locks") -Filter "*.lock" -ErrorAction SilentlyContinue).Count
    $counts = Get-TaskStatusCounts

    Write-Host ""
    Write-Host "Dry-run post-run verification"
    Write-Host "Batch report: $reportPath"
    Write-Host "Locks remaining: $remainingLocks"
    foreach ($entry in $counts.GetEnumerator()) {
        Write-Host "$($entry.Key): $($entry.Value)"
    }

    if ($remainingLocks -ne 0) {
        throw "Dry-run verification failed: lock files remain in workspace\\locks."
    }
}
