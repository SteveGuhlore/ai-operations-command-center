param([Parameter(Mandatory=$true)][string]$TaskId)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
$lockPath = Join-Path $root "workspace\locks\$TaskId.lock"

if (Test-Path $lockPath) {
    Remove-Item $lockPath -Force
    Write-AgentLog "lock-release" "Released lock $TaskId"
} else {
    Write-AgentLog "lock-release" "No lock found for $TaskId"
}
