import pytest
from runner.tools.code import run_powershell, TOOL_SPEC


def test_run_powershell_returns_stdout():
    result = run_powershell(command='Write-Output "hello"')
    assert result["stdout"].strip() == "hello"
    assert result["exit_code"] == 0


def test_run_powershell_captures_stderr():
    result = run_powershell(command="Get-Item C:\\nonexistent_path_xyz_abc")
    assert result["exit_code"] != 0 or "error" in result.get("stderr", "").lower() or result["stdout"] == ""


def test_run_powershell_times_out():
    result = run_powershell(command="Start-Sleep -Seconds 60", timeout=2)
    assert "timeout" in result.get("error", "").lower() or result["exit_code"] != 0


def test_forbidden_commands_are_blocked():
    for cmd in ["rm -rf /", "Remove-Item -Recurse -Force C:\\"]:
        result = run_powershell(command=cmd)
        assert "error" in result or result.get("blocked") is True


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "code_runner"
    assert "input_schema" in TOOL_SPEC
