# Safety hook: blocks destructive commands before they run
# Receives hook JSON on stdin, outputs JSON decision

$raw = [Console]::In.ReadToEnd()
try {
    $data = $raw | ConvertFrom-Json
    $command = $data.tool_input.command
} catch {
    exit 0
}

if (-not $command) { exit 0 }

$dangerousPatterns = @(
    # Unix-style recursive force delete
    'rm\s+-[rRfF]*[fF][rR]?(\s|$)',
    'rm\s+--recursive',
    # PowerShell recursive force delete
    'Remove-Item\b.*-Recurse\b.*-Force\b',
    'Remove-Item\b.*-Force\b.*-Recurse\b',
    # SQL destructive DDL
    '\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b',
    '\bTRUNCATE\s+TABLE\b',
    # Git dangerous operations
    '\bgit\s+reset\s+--hard\b',
    '\bgit\s+push\b.*--force\b',
    '\bgit\s+push\b.*\s-f(\s|$)',
    '\bgit\s+clean\s+.*-f\b',
    '\bgit\s+branch\s+-[Dd]\s',
    # Windows destructive commands
    '\bdel\s+/[sfSF]',
    '\brd\s+/[sqSQ]',
    'format\s+[a-zA-Z]:',
    # Recursive Windows remove
    'rmdir\s+/[sqSQ]'
)

foreach ($pattern in $dangerousPatterns) {
    if ($command -imatch $pattern) {
        @{
            hookSpecificOutput = @{
                hookEventName           = "PreToolUse"
                permissionDecision      = "deny"
                permissionDecisionReason = "SAFETY BLOCK: Dangerous pattern detected in command. Explicitly confirm your intent and I will proceed. Command was: $command"
            }
        } | ConvertTo-Json -Compress -Depth 3
        exit 0
    }
}
