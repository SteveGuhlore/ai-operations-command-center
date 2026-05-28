param([string]$ConfigPath = "config\agents.example.yaml")

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"
. "$PSScriptRoot\lib\CommandCenterValidation.ps1"

$root = Get-CommandCenterRoot
$path = Join-Path $root $ConfigPath
$content = Read-TextFileSafe $path
$errors = @()

if ($content -notmatch "(?m)^agents:\s*$") {
    $errors += "Missing top-level 'agents' section."
}

$items = [regex]::Split($content, "(?m)^\s{2}-\s+role_id:\s*") | Select-Object -Skip 1

if ($items.Count -eq 0) {
    $errors += "No agent entries found."
}

$requiredFields = @(
    "display_name",
    "purpose",
    "allowed_task_types",
    "forbidden_task_types",
    "default_model_label",
    "max_retries",
    "requires_human_approval_for",
    "notes"
)

foreach ($item in $items) {
    $roleIdMatch = [regex]::Match($item, "^(?<id>[^\r\n]+)")
    $roleId = if ($roleIdMatch.Success) { $roleIdMatch.Groups["id"].Value.Trim() } else { "<unknown>" }

    foreach ($field in $requiredFields) {
        if ($item -notmatch "(?m)^\s{4}$([regex]::Escape($field)):\s*") {
            $errors += "Agent '$roleId' is missing required field '$field'."
        }
    }
}

Write-Host "Agent config: $ConfigPath"
Write-Host "Entries found: $($items.Count)"

if ($errors.Count -gt 0) {
    Write-Host "Validation result: FAIL"
    $errors | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Validation result: PASS"
exit 0
