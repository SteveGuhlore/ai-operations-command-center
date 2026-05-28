function Read-TextFileSafe {
    param([Parameter(Mandatory=$true)][string]$Path)
    if (-not (Test-Path $Path)) { throw "Missing file: $Path" }
    return Get-Content $Path -Raw
}

function Get-SimpleYamlValue {
    param(
        [Parameter(Mandatory=$true)][string]$Content,
        [Parameter(Mandatory=$true)][string]$Key
    )
    $pattern = "(?m)^$([regex]::Escape($Key)):\s*(.+?)\s*$"
    $m = [regex]::Match($Content, $pattern)
    if ($m.Success) { return $m.Groups[1].Value.Trim().Trim('"').Trim("'") }
    return $null
}

function Get-TaskFrontmatterValue {
    param(
        [Parameter(Mandatory=$true)][string]$TaskText,
        [Parameter(Mandatory=$true)][string]$Key
    )
    $pattern = "(?m)^$([regex]::Escape($Key)):\s*(.+?)\s*$"
    $m = [regex]::Match($TaskText, $pattern)
    if ($m.Success) { return $m.Groups[1].Value.Trim() }
    return $null
}

function Assert-AllowedAgent {
    param([string]$Agent)
    if ($Agent -notin @("heavy_worker", "debug_worker")) {
        throw "Invalid assigned_agent '$Agent'. Expected 'heavy_worker' or 'debug_worker'."
    }
}
