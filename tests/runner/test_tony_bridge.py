import json
from pathlib import Path
from datetime import date
from runner.bridge import tony_bridge as bridge_module


SAMPLE_SCANNER = {
    "date": "2026-05-21",
    "type": "scanner",
    "tickers": ["AAPL", "TSLA"],
    "notes": "High momentum setups identified.",
}


def test_scanner_file_creates_task(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge" / "tony-stocks"
    tasks_dir = tmp_path / "workspace" / "tasks" / "todo"
    bridge_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)

    monkeypatch.setattr(bridge_module, "BRIDGE_DIR", bridge_dir)
    monkeypatch.setattr(bridge_module, "TASKS_DIR", tasks_dir)

    scanner_file = bridge_dir / f"scanner-{date.today()}.json"
    scanner_file.write_text(json.dumps(SAMPLE_SCANNER), encoding="utf-8")

    bridge_module.process_bridge_file(scanner_file)

    task_files = list(tasks_dir.glob("*.md"))
    assert len(task_files) == 1
    content = task_files[0].read_text(encoding="utf-8")
    assert "stock_research_pod" in content
    assert "AAPL" in content


def test_process_bridge_file_skips_unknown_type(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    tasks_dir = tmp_path / "tasks"
    bridge_dir.mkdir()
    tasks_dir.mkdir()
    monkeypatch.setattr(bridge_module, "BRIDGE_DIR", bridge_dir)
    monkeypatch.setattr(bridge_module, "TASKS_DIR", tasks_dir)

    bad_file = bridge_dir / "unknown-2026-05-21.json"
    bad_file.write_text(json.dumps({"type": "unknown", "data": {}}))
    bridge_module.process_bridge_file(bad_file)  # should not raise or create tasks
    assert len(list(tasks_dir.glob("*.md"))) == 0


def test_scan_and_process_handles_multiple_files(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    tasks_dir = tmp_path / "tasks"
    bridge_dir.mkdir()
    tasks_dir.mkdir()
    monkeypatch.setattr(bridge_module, "BRIDGE_DIR", bridge_dir)
    monkeypatch.setattr(bridge_module, "TASKS_DIR", tasks_dir)

    for i in range(3):
        f = bridge_dir / f"scanner-2026-05-{i+1:02d}.json"
        f.write_text(json.dumps({**SAMPLE_SCANNER, "date": f"2026-05-{i+1:02d}"}))

    bridge_module.scan_and_process()
    assert len(list(tasks_dir.glob("*.md"))) == 3
