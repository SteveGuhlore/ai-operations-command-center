# tests/runner/test_poc_sandbox.py
import importlib

import pytest


def _fresh(tmp_path, monkeypatch):
    import runner.tools.poc_sandbox as ps
    importlib.reload(ps)
    monkeypatch.setattr(ps, "POC_ROOT", tmp_path / "poc")
    return ps


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
    # A blocked slug must never create a directory.
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
    # The destructive command must not have run.
    assert "exit_code" not in res


def test_timeout_kills_command(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    res = ps.poc_runner(slug="demo", command="Start-Sleep -Seconds 10", timeout=2)
    assert res.get("error") == "timeout exceeded"
    assert res.get("exit_code") == -1
