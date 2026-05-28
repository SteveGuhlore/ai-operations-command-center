param(
    [string]$ConfigPath = "config\revenue-pods.example.yaml",
    [string]$AgentsConfigPath = "config\agents.example.yaml",
    [string]$ToolsConfigPath = "config\tools.example.yaml"
)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"
. "$PSScriptRoot\lib\CommandCenterValidation.ps1"

$root = Get-CommandCenterRoot
$configFullPath = Join-Path $root $ConfigPath
$agentsFullPath = Join-Path $root $AgentsConfigPath
$toolsFullPath = Join-Path $root $ToolsConfigPath

$content = Read-TextFileSafe $configFullPath
$agentsContent = Read-TextFileSafe $agentsFullPath
$toolsContent = Read-TextFileSafe $toolsFullPath
$errors = @()

if ($content -notmatch "(?m)^revenue_pods:\s*$") {
    $errors += "Missing top-level 'revenue_pods' section."
}

$knownAgentRoles = @([regex]::Matches($agentsContent, "(?m)^\s{2}-\s+role_id:\s*(.+?)\s*$") | ForEach-Object { $_.Groups[1].Value.Trim() })
$knownTools = @([regex]::Matches($toolsContent, "(?m)^\s{2}-\s+tool_id:\s*(.+?)\s*$") | ForEach-Object { $_.Groups[1].Value.Trim() })

$items = [regex]::Split($content, "(?m)^\s{2}-\s+pod_id:\s*") | Select-Object -Skip 1

if ($items.Count -eq 0) {
    $errors += "No revenue pod entries found."
}

$requiredFields = @(
    "display_name",
    "monetization_model",
    "primary_goal",
    "assigned_agents",
    "required_tools",
    "allowed_task_types",
    "forbidden_task_types",
    "approval_required_for",
    "success_metrics",
    "risk_notes",
    "first_safe_tasks"
)

$seenPodIds = @{}

foreach ($item in $items) {
    $podIdMatch = [regex]::Match($item, "^(?<id>[^\r\n]+)")
    $podId = if ($podIdMatch.Success) { $podIdMatch.Groups["id"].Value.Trim() } else { "<unknown>" }

    if ($seenPodIds.ContainsKey($podId)) {
        $errors += "Duplicate pod_id '$podId'."
    } else {
        $seenPodIds[$podId] = $true
    }

    foreach ($field in $requiredFields) {
        if ($item -notmatch "(?m)^\s{4}$([regex]::Escape($field)):\s*") {
            $errors += "Revenue pod '$podId' is missing required field '$field'."
        }
    }

    $assignedAgentsSection = [regex]::Match($item, "(?m)^\s{4}assigned_agents:\r?\n(?<body>(?:^\s{6}-.*\r?\n?)+)")
    if (-not $assignedAgentsSection.Success) {
        $errors += "Revenue pod '$podId' has an empty or malformed 'assigned_agents' list."
    } else {
        $assignedAgents = @([regex]::Matches($assignedAgentsSection.Groups["body"].Value, "(?m)^\s{6}-\s*(.+?)\s*$") | ForEach-Object { $_.Groups[1].Value.Trim() })
        foreach ($agent in $assignedAgents) {
            if ($knownAgentRoles -notcontains $agent) {
                $errors += "Revenue pod '$podId' references unknown agent role '$agent'."
            }
        }
    }

    $requiredToolsSection = [regex]::Match($item, "(?m)^\s{4}required_tools:\r?\n(?<body>(?:^\s{6}-.*\r?\n?)+)")
    if (-not $requiredToolsSection.Success) {
        $errors += "Revenue pod '$podId' has an empty or malformed 'required_tools' list."
    } else {
        $requiredTools = @([regex]::Matches($requiredToolsSection.Groups["body"].Value, "(?m)^\s{6}-\s*(.+?)\s*$") | ForEach-Object { $_.Groups[1].Value.Trim() })
        foreach ($tool in $requiredTools) {
            if ($knownTools -notcontains $tool) {
                $errors += "Revenue pod '$podId' references unknown tool '$tool'."
            }
        }
    }

    $approvalSection = [regex]::Match($item, "(?m)^\s{4}approval_required_for:\r?\n(?<body>(?:^\s{6}-.*\r?\n?)+)")
    if (-not $approvalSection.Success) {
        $errors += "Revenue pod '$podId' must have a non-empty 'approval_required_for' list."
    }

    $firstSafeTasksSection = [regex]::Match($item, "(?m)^\s{4}first_safe_tasks:\r?\n(?<body>(?:^\s{6}-.*\r?\n?)+)")
    if (-not $firstSafeTasksSection.Success) {
        $errors += "Revenue pod '$podId' must have a non-empty 'first_safe_tasks' list."
    }
}

Write-Host "Revenue pod config: $ConfigPath"
Write-Host "Entries found: $($items.Count)"

if ($errors.Count -gt 0) {
    Write-Host "Validation result: FAIL"
    $errors | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Validation result: PASS"
exit 0
