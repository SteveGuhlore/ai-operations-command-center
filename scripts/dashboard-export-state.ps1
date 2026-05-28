. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

function Get-RoleBlocks {
    param([string]$Content)
    return [regex]::Split($Content, "(?m)^\s{2}-\s+role_id:\s*") | Select-Object -Skip 1
}

function Get-PodBlocks {
    param([string]$Content)
    return [regex]::Split($Content, "(?m)^\s{2}-\s+pod_id:\s*") | Select-Object -Skip 1
}

function Get-FieldValue {
    param(
        [string]$Block,
        [string]$Field
    )
    $match = [regex]::Match($Block, "(?m)^\s{4}$([regex]::Escape($Field)):\s*(.+?)\s*$")
    if ($match.Success) { return $match.Groups[1].Value.Trim() }
    return $null
}

function Get-ListValues {
    param(
        [string]$Block,
        [string]$Field
    )
    $section = [regex]::Match($Block, "(?m)^\s{4}$([regex]::Escape($Field)):\r?\n(?<body>(?:^\s{6}-.*\r?\n?)+)")
    if (-not $section.Success) { return @() }
    return @([regex]::Matches($section.Groups["body"].Value, "(?m)^\s{6}-\s*(.+?)\s*$") | ForEach-Object { $_.Groups[1].Value.Trim() })
}

function Get-OfficeStatus {
    param(
        [string]$TaskStatus,
        [string]$TaskName
    )
    $lowerName = if ($TaskName) { $TaskName.ToLowerInvariant() } else { "" }
    if ($lowerName -match "research") { return "researching" }
    if ($lowerName -match "writing|docs|content") { return "writing" }

    switch ($TaskStatus) {
        "todo" { return "idle" }
        "in_progress" { return "executing" }
        "review" { return "syncing" }
        "done" { return "idle" }
        "failed" { return "error" }
        default { return "idle" }
    }
}

$root = Get-CommandCenterRoot
$dashboardDir = Join-Path $root "workspace\dashboard"
New-Item -ItemType Directory -Force -Path $dashboardDir | Out-Null

$agentsContent = Get-Content (Join-Path $root "config\agents.example.yaml") -Raw
$podsContent = Get-Content (Join-Path $root "config\revenue-pods.example.yaml") -Raw

$statusNames = "todo","in_progress","review","done","failed"
$taskEntries = @()
$taskCounts = [ordered]@{}

foreach ($status in $statusNames) {
    $dir = Join-Path $root "workspace\tasks\$status"
    $tasks = @(Get-ChildItem $dir -Filter "*.md" -ErrorAction SilentlyContinue)
    $taskCounts[$status] = $tasks.Count

    foreach ($task in $tasks) {
        $raw = Get-Content $task.FullName -Raw
        $assignedAgent = $null
        $agentMatch = [regex]::Match($raw, "(?m)^assigned_agent:\s*(.+?)\s*$")
        if ($agentMatch.Success) { $assignedAgent = $agentMatch.Groups[1].Value.Trim() }

        $taskId = Get-TaskIdFromFile $task.FullName
        $taskEntries += [pscustomobject]@{
            task_id = $taskId
            name = $task.Name
            status = $status
            assigned_agent = $assignedAgent
        }
    }
}

$locks = @(Get-ChildItem (Join-Path $root "workspace\locks") -Filter "*.lock" -ErrorAction SilentlyContinue | ForEach-Object {
    [pscustomobject]@{
        name = $_.Name
        last_write_time = $_.LastWriteTime.ToString("o")
    }
})

$recentRuns = @(Get-ChildItem (Join-Path $root "workspace\runs") -Filter "*.md" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 10 |
    ForEach-Object {
        [pscustomobject]@{
            name = $_.Name
            last_write_time = $_.LastWriteTime.ToString("o")
        }
    })

$podBlocks = Get-PodBlocks $podsContent
$revenuePods = @()
foreach ($block in $podBlocks) {
    $podIdMatch = [regex]::Match($block, "^(?<id>[^\r\n]+)")
    $podId = if ($podIdMatch.Success) { $podIdMatch.Groups["id"].Value.Trim() } else { "" }
    $displayName = Get-FieldValue $block "display_name"
    $assignedAgents = Get-ListValues $block "assigned_agents"
    $podTaskCount = @($taskEntries | Where-Object { $_.name -match [regex]::Escape(($podId -replace "_pod$","" -replace "_"," ")) }).Count

    $revenuePods += [pscustomobject]@{
        pod_id = $podId
        display_name = $displayName
        status = "planning"
        assigned_agents = $assignedAgents
        task_count = $podTaskCount
    }
}

$roleBlocks = Get-RoleBlocks $agentsContent
$agents = @()
foreach ($block in $roleBlocks) {
    $roleIdMatch = [regex]::Match($block, "^(?<id>[^\r\n]+)")
    $roleId = if ($roleIdMatch.Success) { $roleIdMatch.Groups["id"].Value.Trim() } else { "" }
    $displayName = Get-FieldValue $block "display_name"
    $modelLabel = Get-FieldValue $block "default_model_label"
    $enabledValue = Get-FieldValue $block "enabled"
    $isEnabled = if ($enabledValue) { $enabledValue } else { "true" }

    $currentTask = $taskEntries |
        Where-Object { $_.assigned_agent -eq $roleId } |
        Sort-Object @{Expression = {
            switch ($_.status) {
                "in_progress" { 0 }
                "review" { 1 }
                "todo" { 2 }
                "done" { 3 }
                "failed" { 4 }
                default { 9 }
            }
        }} |
        Select-Object -First 1

    $podAssignments = @($revenuePods | Where-Object { $_.assigned_agents -contains $roleId } | ForEach-Object { $_.display_name })
    $podAssignment = if ($podAssignments.Count -eq 0) { "core" } elseif ($podAssignments.Count -eq 1) { $podAssignments[0] } else { "multiple" }

    $officeStatus = if ($currentTask) { Get-OfficeStatus -TaskStatus $currentTask.status -TaskName $currentTask.name } else { "idle" }
    $healthState = if ($isEnabled -eq "false") { "disabled" } elseif ($officeStatus -eq "error") { "warning" } else { "healthy" }

    $agents += [pscustomobject]@{
        role_id = $roleId
        display_name = $displayName
        office_status = $officeStatus
        current_task = if ($currentTask) { $currentTask.name } else { $null }
        pod_assignment = $podAssignment
        model_label = $modelLabel
        health_state = $healthState
    }
}

$alerts = @()
if ($locks.Count -gt 0) {
    $alerts += [pscustomobject]@{ level = "warning"; message = "Lock files remain in workspace\\locks." }
}
if ($taskCounts["failed"] -gt 0) {
    $alerts += [pscustomobject]@{ level = "warning"; message = "One or more tasks are in failed status." }
}
if ($taskCounts["in_progress"] -gt 0) {
    $alerts += [pscustomobject]@{ level = "warning"; message = "One or more tasks are still in progress." }
}
if ($alerts.Count -eq 0) {
    $alerts += [pscustomobject]@{ level = "info"; message = "No active dashboard alerts." }
}

$state = [ordered]@{
    generated_at = (Get-Date).ToString("o")
    shell = "Star Office UI"
    backend_source_of_truth = "command_center"
    agents = $agents
    statuses = [ordered]@{
        todo = "idle"
        in_progress = "executing"
        review = "syncing"
        done = "idle"
        failed = "error"
    }
    current_tasks = $taskEntries
    task_counts = $taskCounts
    locks = $locks
    recent_runs = $recentRuns
    revenue_pods = $revenuePods
    alerts = $alerts
    daemon_state = [ordered]@{
        status = "stubbed"
        note = "Scheduler/daemon integration is not active yet."
    }
    budget_state = [ordered]@{
        status = "stubbed"
        note = "Budget bridge is not active yet."
    }
    future_integration_placeholders = @(
        "OpenRouter",
        "Antigravity/Codex",
        "NotebookLM-style KB",
        "provider routing",
        "scheduler/daemon"
    )
}

$outputPath = Join-Path $dashboardDir "dashboard-state.json"
$state | ConvertTo-Json -Depth 8 | Set-Content -Path $outputPath

Write-Host "Dashboard state exported."
Write-Host "Output: $outputPath"
exit 0
