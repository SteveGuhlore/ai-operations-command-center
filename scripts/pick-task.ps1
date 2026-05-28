param([string]$Worker = "worker", [string]$Agent = "")

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
$todoDir = Join-Path $root "workspace\tasks\todo"
$lockDir = Join-Path $root "workspace\locks"
New-Item -ItemType Directory -Force -Path $lockDir | Out-Null

$tasks = Get-ChildItem $todoDir -Filter "*.md" -ErrorAction SilentlyContinue | Sort-Object Name

foreach ($task in $tasks) {
    $taskId = Get-TaskIdFromFile $task.FullName
    $lockPath = Join-Path $lockDir "$taskId.lock"

    if (Test-Path $lockPath) { continue }

    $raw = Get-Content $task.FullName -Raw
    if ($Agent -and ($raw -notmatch "assigned_agent:\s*$Agent")) { continue }

    $lockData = @{
        task_id = $taskId
        worker = $Worker
        agent = $Agent
        created_at = (Get-Date).ToString("o")
    } | ConvertTo-Json

    Set-Content -Path $lockPath -Value $lockData
    Write-AgentLog $Worker "Locked task $taskId"
    Write-Output $task.FullName
    exit 0
}

Write-AgentLog $Worker "No available task found"
exit 1
