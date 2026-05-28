function Get-CommandCenterRoot {
    return (Resolve-Path "$PSScriptRoot\..\..").Path
}

function Get-AgentDisplayName {
    param([string]$Role)
    switch ($Role) {
        "manager" { return "Atlas" }
        "heavy_worker" { return "Forge" }
        "debug_worker" { return "Scout" }
        default { return $Role }
    }
}

function Write-AgentLog {
    param([string]$Worker, [string]$Message)
    $root = Get-CommandCenterRoot
    $logDir = Join-Path $root "workspace\logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp][$Worker] $Message"
    Add-Content -Path (Join-Path $logDir "agent-command-center.log") -Value $line
    Write-Host $line
}

function Get-TaskIdFromFile {
    param([string]$TaskFile)
    $name = Split-Path $TaskFile -Leaf
    if ($name -match "^(?<id>[A-Z]+-\d+)") { return $Matches.id }
    return [System.IO.Path]::GetFileNameWithoutExtension($name)
}
