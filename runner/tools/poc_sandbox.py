# runner/tools/poc_sandbox.py
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from runner.ledger.budget import get_poc_cap, get_poc_run_cost
from runner.tools.code import _is_forbidden

POC_ROOT = Path(__file__).parent.parent.parent / "workspace" / "poc"

# Per-slug accumulated-cost ledger. Mirrors the spawn-decisions/spawn-history
# pattern: derive the path from LEDGER_DIR at call time (not bound at import) so
# a test that monkeypatches LEDGER_DIR stays isolated in its tmp dir.
LEDGER_DIR = Path(__file__).parent.parent.parent / "workspace" / "ledger"
POC_SPEND_NAME = "poc-spend.json"

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


# ── PoC-specific forbidden patterns ───────────────────────────────────────────
# These SUPPLEMENT the shared `_is_forbidden` filter (rm -rf, Format-Volume,
# Clear-Disk, dd) without touching it — code_runner keeps its current behavior;
# only the higher-risk PoC subprocess surface gets this stricter screen.
#
# Each entry is (compiled_regex, why). Patterns use lookaheads so flag order does
# not matter (e.g. -Recurse before/after -Force). All match case-insensitively.
def _ci(pattern: str) -> "re.Pattern[str]":
    return re.compile(pattern, re.IGNORECASE)


_POC_FORBIDDEN: list[tuple["re.Pattern[str]", str]] = [
    # ── Network egress (PowerShell) ──────────────────────────────────────────
    # A PoC is meant to scaffold/demo locally; it has no business reaching the
    # network. Blocking egress stops exfiltration and remote-payload download.
    (_ci(r"\bInvoke-WebRequest\b"), "network egress: Invoke-WebRequest"),
    (_ci(r"\bInvoke-RestMethod\b"), "network egress: Invoke-RestMethod"),
    (_ci(r"\biwr\b"),               "network egress: iwr (Invoke-WebRequest alias)"),
    (_ci(r"\birm\b"),               "network egress: irm (Invoke-RestMethod alias)"),
    (_ci(r"\bcurl\b"),              "network egress: curl (PS alias for Invoke-WebRequest)"),
    (_ci(r"\bwget\b"),              "network egress: wget (PS alias for Invoke-WebRequest)"),
    (_ci(r"\bTest-NetConnection\b"), "network probe: Test-NetConnection"),
    (_ci(r"\btnc\b"),               "network probe: tnc (Test-NetConnection alias)"),
    (_ci(r"\bStart-BitsTransfer\b"), "network egress: Start-BitsTransfer (background download)"),
    (_ci(r"System\.Net\.WebClient"), "network egress: System.Net.WebClient"),
    (_ci(r"\bNet\.WebClient\b"),     "network egress: Net.WebClient"),
    (_ci(r"\bDownloadString\b"),     "network egress: WebClient.DownloadString (download cradle)"),
    (_ci(r"\bDownloadFile\b"),       "network egress: WebClient.DownloadFile (download cradle)"),
    (_ci(r"Net\.Sockets"),           "network egress: System.Net.Sockets raw socket"),
    # ── Network egress (Python invoked from the PoC shell) ───────────────────
    (_ci(r"\bimport\s+socket\b"),    "network egress: python import socket"),
    (_ci(r"\bsocket\.socket\b"),     "network egress: python socket.socket"),
    (_ci(r"\bimport\s+urllib\b"),    "network egress: python import urllib"),
    (_ci(r"\bfrom\s+urllib\b"),      "network egress: python from urllib import"),
    (_ci(r"\burllib\.request\b"),    "network egress: python urllib.request"),
    (_ci(r"\bimport\s+requests\b"),  "network egress: python import requests"),
    (_ci(r"\brequests\.(get|post|put|delete|head|patch|request)\b"), "network egress: python requests call"),
    (_ci(r"\bimport\s+httpx\b"),     "network egress: python import httpx"),
    (_ci(r"\bhttpx\.(get|post|put|delete|head|patch|Client|AsyncClient)\b"), "network egress: python httpx call"),
    # ── Destructive filesystem (Windows-flavored) ────────────────────────────
    # Recursive force-delete can wipe far beyond the slug dir if a path arg
    # escapes; a sandboxed PoC never needs it.
    (_ci(r"Remove-Item(?=[\s\S]*-Recurse)(?=[\s\S]*-Force)"), "destructive: Remove-Item -Recurse -Force"),
    (_ci(r"\bdel\s+(?:/[fsqFSQ]\s*)+"),  "destructive: del /f /s /q"),
    (_ci(r"\brd\s+/s\b"),                "destructive: rd /s (recursive dir remove)"),
    (_ci(r"\brmdir\s+/s\b"),             "destructive: rmdir /s (recursive dir remove)"),
    # ── Registry edits ───────────────────────────────────────────────────────
    # Writing HKLM is machine-wide persistence/config tampering — out of scope
    # for a demo and a classic persistence vector.
    (_ci(r"\breg\s+(?:add|delete|import)\b[\s\S]*HK(?:LM|EY_LOCAL_MACHINE)"), "registry tamper: reg add/delete HKLM"),
    (_ci(r"(?:Set|New|Remove)-ItemProperty[\s\S]*HKLM:"), "registry tamper: *-ItemProperty HKLM:"),
    (_ci(r"\bNew-Item[\s\S]*HKLM:"),     "registry tamper: New-Item HKLM:"),
    # ── Scheduled-task / persistence abuse ───────────────────────────────────
    (_ci(r"\bschtasks\b(?=[\s\S]*/create)"), "persistence: schtasks /create"),
    (_ci(r"\bRegister-ScheduledTask\b"),     "persistence: Register-ScheduledTask"),
    # ── Process kill ─────────────────────────────────────────────────────────
    # Force-killing processes could take down the runner or the running app.
    (_ci(r"\btaskkill\b(?=[\s\S]*/f)"),       "process kill: taskkill /f"),
    (_ci(r"\bStop-Process\b(?=[\s\S]*-Force)"), "process kill: Stop-Process -Force"),
    # ── Credential theft ─────────────────────────────────────────────────────
    (_ci(r"\bGet-Credential\b"),             "credential access: Get-Credential prompt/harvest"),
    (_ci(r"\bConvertFrom-SecureString\b"),   "credential theft: ConvertFrom-SecureString (dumps secrets to plaintext)"),
    (_ci(r"System\.Net\.NetworkCredential"), "credential theft: NetworkCredential plaintext access"),
    # ── Obfuscated / encoded execution ───────────────────────────────────────
    # -EncodedCommand runs base64-packed scripts that bypass the text filter
    # entirely, so the encoded form itself must be refused.
    (_ci(r"-encodedcommand\b"),              "obfuscation: -EncodedCommand (base64 payload)"),
    (_ci(r"-enc\s+[A-Za-z0-9+/=]{16,}"),     "obfuscation: -enc <base64 payload>"),
]


def _poc_forbidden(command: str) -> str | None:
    """Return the rationale string of the first matching block reason, or None.
    Checks the shared destructive filter first, then the PoC-specific list."""
    if _is_forbidden(command):
        return "shared safety filter (destructive command)"
    for pattern, why in _POC_FORBIDDEN:
        if pattern.search(command):
            return why
    return None


def _safe_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug)) and ".." not in slug


# ── Per-slug spend ledger ─────────────────────────────────────────────────────

def _spend_file() -> Path:
    return LEDGER_DIR / POC_SPEND_NAME


def read_poc_spend() -> dict:
    """Full per-slug spend ledger: {by_slug: {slug: {accumulated_usd, runs,
    last_run}}}. Tolerates a missing or corrupt file (returns empty)."""
    path = _spend_file()
    if not path.exists():
        return {"by_slug": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"by_slug": {}}
    data.setdefault("by_slug", {})
    return data


def get_poc_spend(slug: str) -> float:
    return read_poc_spend()["by_slug"].get(slug, {}).get("accumulated_usd", 0.0)


def _charge_poc(slug: str, cost: float) -> float:
    """Add `cost` to the slug's accumulated envelope spend and persist. Returns
    the new accumulated total."""
    data = read_poc_spend()
    entry = data["by_slug"].setdefault(slug, {"accumulated_usd": 0.0, "runs": 0, "last_run": None})
    entry["accumulated_usd"] = round(entry["accumulated_usd"] + cost, 6)
    entry["runs"] += 1
    entry["last_run"] = datetime.now().isoformat(timespec="seconds")
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    _spend_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return entry["accumulated_usd"]


# Env overrides that strip the inherited proxy config inside the subprocess.
# Honest limit: this does NOT seal the network — a process making a direct
# connection ignores these. It removes any ambient proxy so a misconfigured
# tool can't tunnel out via a parent proxy; the real egress defense is the
# deny-list above.
_EGRESS_ENV = {
    "HTTP_PROXY": "", "HTTPS_PROXY": "", "NO_PROXY": "*",
    "http_proxy": "", "https_proxy": "", "no_proxy": "*",
}


def poc_runner(slug: str, command: str, timeout: int = 30) -> dict:
    if not _safe_slug(slug):
        return {"blocked": True, "error": f"Invalid slug: {slug!r}"}

    reason = _poc_forbidden(command)
    if reason is not None:
        return {"blocked": True, "error": f"Command blocked by safety filter ({reason})"}

    # Mid-run hard dollar meter: refuse BEFORE spawning if this slug has already
    # spent its envelope. Checked per invocation, not just between tasks.
    cap = get_poc_cap()
    spent = get_poc_spend(slug)
    if spent >= cap:
        return {
            "blocked": True,
            "error": f"PoC budget exceeded for {slug!r}: ${spent:.2f} spent of ${cap:.2f} cap",
            "accumulated_usd": spent,
            "cap_usd": cap,
        }

    workdir = POC_ROOT / slug
    workdir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **_EGRESS_ENV}
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout, cwd=str(workdir), env=env,
        )
        accumulated = _charge_poc(slug, get_poc_run_cost())
        return {
            "stdout": result.stdout[:8000],
            "stderr": result.stderr[:4000],
            "exit_code": result.returncode,
            "workdir": str(workdir),
            "accumulated_usd": accumulated,
            "cap_usd": cap,
        }
    except subprocess.TimeoutExpired:
        accumulated = _charge_poc(slug, get_poc_run_cost())
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": "timeout exceeded",
                "accumulated_usd": accumulated, "cap_usd": cap}
    except OSError as exc:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": str(exc)}


TOOL_SPEC = {
    "name": "poc_runner",
    "description": (
        "Run a PowerShell command for a proof-of-concept, confined to workspace/poc/<slug>/. "
        "Use this (not code_runner) to scaffold and run PoC demos. The working directory is the slug "
        "folder; write files there with relative paths. No directory escape. Subprocess timeout enforced. "
        "Network access, destructive/registry/persistence commands are blocked, and each slug has a hard "
        "per-PoC dollar cap — runs are refused once the envelope is spent."
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
