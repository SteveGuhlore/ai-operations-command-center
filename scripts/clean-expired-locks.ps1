param([int]$ExpiryMinutes = 60)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
$lockDir = Join-Path $root "workspace\locks"
$now = Get-Date

Get-ChildItem $lockDir -Filter "*.lock" -ErrorAction SilentlyContinue | ForEach-Object {
    $age = ($now - $_.LastWriteTime).TotalMinutes
    if ($age -ge $ExpiryMinutes) {
        Write-AgentLog "lock-cleaner" "Removing expired lock $($_.Name), age=$([math]::Round($age,1)) minutes"
        Remove-Item $_.FullName -Force
    }
}
