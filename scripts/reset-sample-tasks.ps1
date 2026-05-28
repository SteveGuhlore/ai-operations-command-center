. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
$todoDir = Join-Path $root "workspace\tasks\todo"
New-Item -ItemType Directory -Force -Path $todoDir | Out-Null

$sourceStatuses = "review", "done", "failed", "in_progress"
$moved = @()

foreach ($status in $sourceStatuses) {
    $sourceDir = Join-Path $root "workspace\tasks\$status"
    $sampleTasks = Get-ChildItem $sourceDir -Filter "SAMPLE-*.md" -ErrorAction SilentlyContinue

    foreach ($task in $sampleTasks) {
        $destination = Join-Path $todoDir $task.Name
        Move-Item -Path $task.FullName -Destination $destination -Force
        $moved += $task.Name
        Write-AgentLog "sample-reset" "Moved $($task.Name) from $status to todo"
    }
}

if ($moved.Count -eq 0) {
    Write-Host "No SAMPLE-* tasks needed resetting."
    exit 0
}

Write-Host "Reset $($moved.Count) SAMPLE-* task(s) back to todo."
$moved | ForEach-Object { Write-Host " - $_" }
exit 0
