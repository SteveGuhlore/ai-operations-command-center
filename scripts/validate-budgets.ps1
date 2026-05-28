param([string]$ConfigPath = "config\budgets.example.yaml")

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"
. "$PSScriptRoot\lib\CommandCenterValidation.ps1"

$root = Get-CommandCenterRoot
$path = Join-Path $root $ConfigPath
$content = Read-TextFileSafe $path
$errors = @()

$requiredTopLevelSections = @(
    "daily_limits",
    "per_role_limits",
    "retry_limits",
    "alert_thresholds",
    "shutdown_threshold"
)

foreach ($section in $requiredTopLevelSections) {
    if ($content -notmatch "(?m)^  $([regex]::Escape($section)):\s*$") {
        $errors += "Missing top-level section '$section'."
    }
}

$requiredDailyLimitFields = @("total_token_limit", "total_spend_limit_usd")
foreach ($field in $requiredDailyLimitFields) {
    if ($content -notmatch "(?m)^    $([regex]::Escape($field)):\s*") {
        $errors += "Missing daily limit field '$field'."
    }
}

$requiredRoles = @(
    "manager",
    "heavy_worker",
    "debug_worker",
    "content_worker",
    "media_worker",
    "audio_worker",
    "guard_worker",
    "budget_worker"
)

foreach ($role in $requiredRoles) {
    if ($content -notmatch "(?m)^    $([regex]::Escape($role)):\s*$") {
        $errors += "Missing per-role budget section for '$role'."
    }
}

$requiredAlertFields = @(
    "warn_at_percent_of_daily_budget",
    "escalate_at_percent_of_daily_budget",
    "pause_noncritical_work_at_percent_of_daily_budget"
)

foreach ($field in $requiredAlertFields) {
    if ($content -notmatch "(?m)^    $([regex]::Escape($field)):\s*") {
        $errors += "Missing alert threshold field '$field'."
    }
}

if ($content -notmatch "(?m)^    stop_all_nonapproved_work_at_percent_of_daily_budget:\s*") {
    $errors += "Missing shutdown threshold field 'stop_all_nonapproved_work_at_percent_of_daily_budget'."
}

Write-Host "Budget config: $ConfigPath"

if ($errors.Count -gt 0) {
    Write-Host "Validation result: FAIL"
    $errors | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Validation result: PASS"
exit 0
