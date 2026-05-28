param([string]$ConfigPath = "config\tools.example.yaml")

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"
. "$PSScriptRoot\lib\CommandCenterValidation.ps1"

$root = Get-CommandCenterRoot
$path = Join-Path $root $ConfigPath
$content = Read-TextFileSafe $path
$errors = @()

if ($content -notmatch "(?m)^tools:\s*$") {
    $errors += "Missing top-level 'tools' section."
}

$items = [regex]::Split($content, "(?m)^\s{2}-\s+tool_id:\s*") | Select-Object -Skip 1

if ($items.Count -eq 0) {
    $errors += "No tool entries found."
}

$requiredFields = @(
    "purpose",
    "allowed_roles",
    "requires_approval",
    "risk_level",
    "notes"
)

foreach ($item in $items) {
    $toolIdMatch = [regex]::Match($item, "^(?<id>[^\r\n]+)")
    $toolId = if ($toolIdMatch.Success) { $toolIdMatch.Groups["id"].Value.Trim() } else { "<unknown>" }

    foreach ($field in $requiredFields) {
        if ($item -notmatch "(?m)^\s{4}$([regex]::Escape($field)):\s*") {
            $errors += "Tool '$toolId' is missing required field '$field'."
        }
    }
}

Write-Host "Tool config: $ConfigPath"
Write-Host "Entries found: $($items.Count)"

if ($errors.Count -gt 0) {
    Write-Host "Validation result: FAIL"
    $errors | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Validation result: PASS"
exit 0
