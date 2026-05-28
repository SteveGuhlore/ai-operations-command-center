. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
$exportScript = Join-Path $PSScriptRoot "dashboard-export-state.ps1"

Write-Host "Dashboard push stub"
Write-Host "Root: $root"
Write-Host ""
Write-Host "This script is intentionally a future bridge stub."
Write-Host "It does not install Star Office UI, connect APIs, or modify execution."
Write-Host ""
& $exportScript | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Dashboard state export failed."
}

Write-Host "Current safe responsibilities:"
Write-Host " - Export command center office state to workspace\\dashboard\\dashboard-state.json"
Write-Host " - Keep Star Office UI integration read-only"
Write-Host ""
Write-Host "Forbidden responsibilities:"
Write-Host " - Deciding tasks"
Write-Host " - Spawning workers"
Write-Host " - Spending money"
Write-Host " - Editing files"
Write-Host ""
Write-Host "Future bridge modes:"
Write-Host " - Star Office UI polling dashboard-state.json"
Write-Host " - Push updates into Star Office UI from this script later"
exit 0
