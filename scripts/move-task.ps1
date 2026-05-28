param(
    [Parameter(Mandatory=$true)][string]$TaskFile,
    [Parameter(Mandatory=$true)][ValidateSet("in_progress","review","done","failed","todo")][string]$Status
)

. "$PSScriptRoot\lib\AgentCommandCenter.ps1"

$root = Get-CommandCenterRoot
$targetDir = Join-Path $root "workspace\tasks\$Status"
New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

$target = Join-Path $targetDir (Split-Path $TaskFile -Leaf)
Move-Item -Path $TaskFile -Destination $target -Force
Write-AgentLog "task-mover" "Moved $(Split-Path $TaskFile -Leaf) to $Status"
Write-Output $target
