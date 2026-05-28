param(
    [Parameter(Mandatory=$true)][ValidateSet("heavy_worker","debug_worker")][string]$Agent,
    [string]$WorkerName = "",
    [switch]$DryRun,
    [int]$MaxTasks = 0
)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

if (-not $WorkerName) { $WorkerName = "$Agent-$PID" }
$agentDisplayName = Get-AgentDisplayName $Agent

Write-AgentLog $WorkerName "Starting auto-agent loop for $agentDisplayName ($Agent). DryRun=$DryRun"

$processedTasks = 0

while ($true) {
    & "$PSScriptRoot\clean-expired-locks.ps1" | Out-Null

    $taskFile = & "$PSScriptRoot\pick-task.ps1" -Worker $WorkerName -Agent $Agent
    if ($LASTEXITCODE -ne 0 -or -not $taskFile) {
        Write-AgentLog $WorkerName "No more tasks. Exiting."
        break
    }

    $taskId = Get-TaskIdFromFile $taskFile
    $sourceTaskName = Split-Path $taskFile -Leaf
    $startingStatus = Split-Path (Split-Path $taskFile -Parent) -Leaf
    $endingStatus = "review"
    $lockCreated = "yes"
    $inProgressFile = & "$PSScriptRoot\move-task.ps1" -TaskFile $taskFile -Status in_progress

    $runLog = Join-Path (Get-CommandCenterRoot) "workspace\runs\$taskId-$WorkerName.md"
    $runLogLines = @(
        "# Run Log - $taskId",
        "",
        "Source task filename: $sourceTaskName",
        "Task id: $taskId",
        "Assigned worker type: $Agent",
        "Assigned worker display name: $agentDisplayName",
        "Worker name: $WorkerName",
        "Started: $(Get-Date)",
        "Starting status: $startingStatus",
        "Ending status: $endingStatus",
        "Lock created: $lockCreated"
    )
    Set-Content -Path $runLog -Value ($runLogLines -join "`n")

    if ($DryRun) {
        Add-Content -Path $runLog -Value "`nDry run only. No AI CLI was called."
        $reviewFile = & "$PSScriptRoot\move-task.ps1" -TaskFile $inProgressFile -Status review
        Write-AgentLog $WorkerName "Dry-run moved $taskId to review with $agentDisplayName ($Agent)"
    } else {
        Add-Content -Path $runLog -Value "`nTODO: Wire this section to the real heavy/debug worker handoff."
        Add-Content -Path $runLog -Value "`nFor now, worker stops at review for manual execution."
        $reviewFile = & "$PSScriptRoot\move-task.ps1" -TaskFile $inProgressFile -Status review
        Write-AgentLog $WorkerName "Moved $taskId to review for manual execution with $agentDisplayName ($Agent)"
    }

    & "$PSScriptRoot\release-lock.ps1" -TaskId $taskId | Out-Null
    Add-Content -Path $runLog -Value "`nLock released: yes"
    $processedTasks += 1

    if ($MaxTasks -gt 0 -and $processedTasks -ge $MaxTasks) {
        Write-AgentLog $WorkerName "Reached MaxTasks=$MaxTasks. Exiting."
        break
    }
}

Write-AgentLog $WorkerName "Auto-agent loop finished."
