# Auto-starts the full AI Ops Command Center (dashboard + cron runner) at user
# logon via a Startup-folder shortcut. No admin required. launch.py has a singleton
# guard, so logging in while it already runs is a harmless no-op. Uses pythonw.exe
# so there is no console window. Re-run to refresh the shortcut.
#
# Usage:   powershell -File scripts/install-autostart.ps1
# Remove:  Remove-Item "$([Environment]::GetFolderPath('Startup'))\AIOpsCommandCenter.lnk"

$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $PSScriptRoot
$Pythonw = 'C:\Users\alexa\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe'
if (-not (Test-Path $Pythonw)) {
    $py = (Get-Command python).Source
    $Pythonw = Join-Path (Split-Path -Parent $py) 'pythonw.exe'
    if (-not (Test-Path $Pythonw)) { $Pythonw = $py }
}

$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'AIOpsCommandCenter.lnk'

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $Pythonw
$lnk.Arguments = 'scripts\launch.py --interval 600'
$lnk.WorkingDirectory = $ProjectDir
$lnk.Description = 'AI Ops Command Center — dashboard + cron runner'
$lnk.WindowStyle = 7
$lnk.Save()

Write-Output "Created startup shortcut: $lnkPath"
Write-Output "Target : $Pythonw scripts\launch.py --interval 600"
Write-Output "Workdir: $ProjectDir"
