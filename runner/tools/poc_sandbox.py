# runner/tools/poc_sandbox.py
import re
import subprocess
from pathlib import Path

from runner.tools.code import _is_forbidden

POC_ROOT = Path(__file__).parent.parent.parent / "workspace" / "poc"

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


def _safe_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug)) and ".." not in slug


def poc_runner(slug: str, command: str, timeout: int = 30) -> dict:
    if not _safe_slug(slug):
        return {"blocked": True, "error": f"Invalid slug: {slug!r}"}
    if _is_forbidden(command):
        return {"blocked": True, "error": "Command blocked by safety filter"}
    workdir = POC_ROOT / slug
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout, cwd=str(workdir),
        )
        return {
            "stdout": result.stdout[:8000],
            "stderr": result.stderr[:4000],
            "exit_code": result.returncode,
            "workdir": str(workdir),
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": "timeout exceeded"}
    except OSError as exc:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": str(exc)}


TOOL_SPEC = {
    "name": "poc_runner",
    "description": (
        "Run a PowerShell command for a proof-of-concept, confined to workspace/poc/<slug>/. "
        "Use this (not code_runner) to scaffold and run PoC demos. The working directory is the slug "
        "folder; write files there with relative paths. No directory escape. Subprocess timeout enforced."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Opportunity slug — the PoC folder name"},
            "command": {"type": "string", "description": "PowerShell command (runs with cwd = the slug folder)"},
            "timeout": {"type": "integer", "description": "Timeout seconds (default 30)", "default": 30},
        },
        "required": ["slug", "command"],
    },
}
