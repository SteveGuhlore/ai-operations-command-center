param([string]$ConfigPath = "config\guardrails.example.yaml")

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"
. "$PSScriptRoot\lib\CommandCenterValidation.ps1"

$root = Get-CommandCenterRoot
$path = Join-Path $root $ConfigPath
$content = Read-TextFileSafe $path
$errors = @()

if ($content -notmatch "(?m)^guardrails:\s*$") {
    $errors += "Missing top-level 'guardrails' section."
}

$items = [regex]::Split($content, "(?m)^\s{2}-\s+rule_id:\s*") | Select-Object -Skip 1

if ($items.Count -eq 0) {
    $errors += "No guardrail entries found."
}

$requiredFields = @(
    "description",
    "enforcement",
    "applies_to_roles"
)

foreach ($item in $items) {
    $ruleIdMatch = [regex]::Match($item, "^(?<id>[^\r\n]+)")
    $ruleId = if ($ruleIdMatch.Success) { $ruleIdMatch.Groups["id"].Value.Trim() } else { "<unknown>" }

    foreach ($field in $requiredFields) {
        if ($item -notmatch "(?m)^\s{4}$([regex]::Escape($field)):\s*") {
            $errors += "Guardrail '$ruleId' is missing required field '$field'."
        }
    }
}

Write-Host "Guardrail config: $ConfigPath"
Write-Host "Entries found: $($items.Count)"

if ($errors.Count -gt 0) {
    Write-Host "Validation result: FAIL"
    $errors | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Validation result: PASS"
exit 0
