. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
$statuses = "todo","in_progress","review","done","failed"

Write-Host "AI Agent Command Center Status"
Write-Host "Root: $root"
Write-Host ""

foreach ($status in $statuses) {
    $dir = Join-Path $root "workspace\tasks\$status"
    $count = @(Get-ChildItem $dir -Filter "*.md" -ErrorAction SilentlyContinue).Count
    Write-Host "$status : $count"
}

$locks = @(Get-ChildItem (Join-Path $root "workspace\locks") -Filter "*.lock" -ErrorAction SilentlyContinue).Count
Write-Host "locks : $locks"
