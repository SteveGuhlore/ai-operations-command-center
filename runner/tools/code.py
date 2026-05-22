import subprocess
import re

FORBIDDEN_PATTERNS = [
    r"rm\s+-rf",
    r"Remove-Item.*-Recurse.*-Force\s+[Cc]:\\?$",
    r"Format-Volume",
    r"Clear-Disk",
    r"dd\s+if=",
]

_FORBIDDEN_RE = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]


def _is_forbidden(command: str) -> bool:
    return any(pattern.search(command) for pattern in _FORBIDDEN_RE)


def run_powershell(command: str, timeout: int = 30) -> dict:
    if _is_forbidden(command):
        return {"blocked": True, "error": f"Command blocked by safety filter: {command[:80]}"}

    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": "timeout exceeded"}
    except OSError as exc:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": str(exc)}


def code_runner(command: str, timeout: int = 30) -> dict:
    return run_powershell(command, timeout)


TOOL_SPEC = {
    "name": "code_runner",
    "description": "Run a PowerShell command in the workspace and return stdout/stderr.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "PowerShell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)", "default": 30},
        },
        "required": ["command"],
    }
}
