param([int]$HeavyWorkers = 1, [int]$DebugWorkers = 1, [switch]$DryRun)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

Write-AgentLog "launcher" "Launching batch. HeavyWorkers=$HeavyWorkers DebugWorkers=$DebugWorkers DryRun=$DryRun"
& "$PSScriptRoot\clean-expired-locks.ps1" | Out-Null

if ($DryRun) {
    Write-AgentLog "launcher" "Dry-run mode simulates task movement in-process. No background worker jobs will be started."

    for ($i = 1; $i -le $HeavyWorkers; $i++) {
        & "$PSScriptRoot\auto-agent.ps1" -Agent heavy_worker -WorkerName "heavy-worker-dryrun-$i" -DryRun -MaxTasks 1
    }

    for ($i = 1; $i -le $DebugWorkers; $i++) {
        & "$PSScriptRoot\auto-agent.ps1" -Agent debug_worker -WorkerName "debug-worker-dryrun-$i" -DryRun -MaxTasks 1
    }

    Write-AgentLog "launcher" "Dry-run simulation finished."
    exit 0
}

$jobs = @()

for ($i = 1; $i -le $HeavyWorkers; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($scriptRoot, $dry)
        & "$scriptRoot\auto-agent.ps1" -Agent heavy_worker -WorkerName "heavy-worker-$PID" -DryRun:$dry
    } -ArgumentList $PSScriptRoot, $DryRun
}

for ($i = 1; $i -le $DebugWorkers; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($scriptRoot, $dry)
        & "$scriptRoot\auto-agent.ps1" -Agent debug_worker -WorkerName "debug-worker-$PID" -DryRun:$dry
    } -ArgumentList $PSScriptRoot, $DryRun
}

Write-AgentLog "launcher" "Started $($jobs.Count) worker jobs."
Write-Host "Use Get-Job, Receive-Job, and Remove-Job to inspect/clean worker jobs."
