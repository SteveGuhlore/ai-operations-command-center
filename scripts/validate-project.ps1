param(
    [string]$ProjectProfile = "projects\sample-project.yaml",
    [switch]$AllowPlaceholderPath
)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"
. "$PSScriptRoot\lib\CommandCenterValidation.ps1"

$root = Get-CommandCenterRoot
$profilePath = Join-Path $root $ProjectProfile
$content = Read-TextFileSafe $profilePath

$projectName = Get-SimpleYamlValue $content "project_name"
$projectPath = Get-SimpleYamlValue $content "project_path"
$autonomy = Get-SimpleYamlValue $content "autonomy_level"
$maxWorkers = Get-SimpleYamlValue $content "max_parallel_workers"
$isPlaceholderPath = $false

if ($projectPath) {
    $placeholderPatterns = @(
        '^PLACEHOLDER',
        '^CHANGE_ME',
        '^EXAMPLE',
        'your-project-path',
        'path/to'
    )

    foreach ($pattern in $placeholderPatterns) {
        if ($projectPath -match $pattern) {
            $isPlaceholderPath = $true
            break
        }
    }
}

$errors = @()
if (-not $projectName) { $errors += "Missing project_name" }
if (-not $projectPath) { $errors += "Missing project_path" }
if (-not $autonomy) { $errors += "Missing autonomy_level" }
if (-not $maxWorkers) { $errors += "Missing max_parallel_workers" }
if ($content -notmatch "(?m)^forbidden_changes:") { $errors += "Missing forbidden_changes list" }
if ($content -notmatch "(?m)^test_commands:") { $errors += "Missing test_commands list" }
if ($content -notmatch "(?m)^read_first:") { $errors += "Missing read_first list" }
if ($projectPath -and $isPlaceholderPath -and -not $AllowPlaceholderPath) {
    $errors += "project_path is a placeholder. Re-run with -AllowPlaceholderPath for foundation-only testing."
}

Write-Host "Project profile: $ProjectProfile"
Write-Host "Project name: $projectName"
Write-Host "Project path: $projectPath"
Write-Host "Autonomy level: $autonomy"
Write-Host "Max workers: $maxWorkers"
if ($projectPath) {
    if ($isPlaceholderPath) {
        if ($AllowPlaceholderPath) {
            Write-Host "Project path mode: placeholder mode allowed for foundation-only testing"
        } else {
            Write-Host "Project path mode: placeholder mode blocked until -AllowPlaceholderPath is supplied"
        }
    } else {
        Write-Host "Project path mode: concrete path provided"
    }
}
Write-Host ""

if ($errors.Count -gt 0) {
    Write-Host "Validation result: FAIL"
    $errors | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Validation result: PASS"
exit 0
