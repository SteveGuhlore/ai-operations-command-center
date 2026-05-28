param(
    [string]$TaskRoot = "",
    [switch]$AllowEmpty
)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"
. "$PSScriptRoot\lib\CommandCenterValidation.ps1"

$root = Get-CommandCenterRoot
$taskDirs = @()

if ($TaskRoot) {
    $taskDirs = @(Join-Path $root $TaskRoot)
} else {
    $taskDirs = @(
        (Join-Path $root "workspace\tasks\todo"),
        (Join-Path $root "workspace\tasks\in_progress"),
        (Join-Path $root "workspace\tasks\review"),
        (Join-Path $root "workspace\tasks\done"),
        (Join-Path $root "workspace\tasks\failed")
    )
}

$errors = @()
$tasks = @()
$scannedDirs = @()

foreach ($taskDir in $taskDirs) {
    $tasks += @(Get-ChildItem $taskDir -Filter "*.md" -ErrorAction SilentlyContinue)
}

if ($tasks.Count -eq 0) {
    if ($AllowEmpty) {
        if ($TaskRoot) {
            Write-Host "No tasks found in $TaskRoot (allowed)."
        } else {
            Write-Host "No tasks found across all status folders (allowed)."
        }
        exit 0
    }

    if ($TaskRoot) {
        Write-Host "No tasks found in $TaskRoot"
    } else {
        Write-Host "No tasks found across workspace\tasks\todo, in_progress, review, done, or failed"
    }
    exit 1
}

foreach ($task in $tasks) {
    $text = Get-Content $task.FullName -Raw
    $taskId = Get-TaskFrontmatterValue $text "task_id"
    $project = Get-TaskFrontmatterValue $text "project"
    $agent = Get-TaskFrontmatterValue $text "assigned_agent"
    $status = Get-TaskFrontmatterValue $text "status"
    $hasAllowedFrontmatter = $text -match "(?m)^allowed_files:\s*$"
    $hasForbiddenFrontmatter = $text -match "(?m)^forbidden_files:\s*$"

    if (-not $taskId) { $errors += "$($task.Name): missing task_id" }
    if (-not $project) { $errors += "$($task.Name): missing project" }
    if (-not $agent) { $errors += "$($task.Name): missing assigned_agent" }
    if (-not $status) { $errors += "$($task.Name): missing status" }

    try { Assert-AllowedAgent $agent } catch { $errors += "$($task.Name): $($_.Exception.Message)" }

    if (-not $hasAllowedFrontmatter) { $errors += "$($task.Name): missing allowed_files frontmatter" }
    if (-not $hasForbiddenFrontmatter) { $errors += "$($task.Name): missing forbidden_files frontmatter" }
    if ($text -notmatch "## Stop conditions") {
        $errors += "$($task.Name): missing stop conditions"
    }
}

if ($TaskRoot) {
    Write-Host "Validated $($tasks.Count) task(s) from $TaskRoot."
} else {
    Write-Host "Validated $($tasks.Count) task(s) across all status folders."
}

if ($errors.Count -gt 0) {
    Write-Host "Task validation: FAIL"
    $errors | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Task validation: PASS"
exit 0
