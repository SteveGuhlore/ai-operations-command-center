# tests/runner/test_vault_memory_guard.py
import importlib


def _fresh(tmp_path, monkeypatch):
    import runner.tools.vault_memory as vm
    importlib.reload(vm)
    monkeypatch.setattr(vm, "AGENTS_MEMORY_DIR", tmp_path / "agents")
    return vm


def test_no_tool_call_run_logged_as_noop(tmp_path, monkeypatch):
    vm = _fresh(tmp_path, monkeypatch)
    vm.auto_write_task_memory("x_worker", "T1", "scan", "success", "(no tool calls made this run)")
    text = (vm.AGENTS_MEMORY_DIR / "x_worker" / "memory.md").read_text(encoding="utf-8")
    assert "noop" in text


def test_errored_run_logged_as_failure(tmp_path, monkeypatch):
    vm = _fresh(tmp_path, monkeypatch)
    vm.auto_write_task_memory("x_worker", "T2", "scan", "success",
                              "Run completed via tool calls: web_research. ALL_TOOLS_ERRORED")
    text = (vm.AGENTS_MEMORY_DIR / "x_worker" / "memory.md").read_text(encoding="utf-8")
    assert "failure" in text
