import json
from runner.bridge import tony_bridge as bridge_module


def _setup(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    tasks_dir = tmp_path / "workspace" / "tasks" / "todo"
    reports_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)
    monkeypatch.setattr(bridge_module, "TRADING_REPORTS_DIR", reports_dir)
    monkeypatch.setattr(bridge_module, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(bridge_module, "_PROCESSED_LOG", tmp_path / "processed.json")
    monkeypatch.setattr(bridge_module, "VAULT_DIR", tmp_path / "vault")
    return reports_dir, tasks_dir


def _write_eod(reports_dir, date_str, tickers):
    d = reports_dir / date_str
    d.mkdir(parents=True, exist_ok=True)
    (d / "eod_report.json").write_text(
        json.dumps({"active_symbols": tickers, "weakening": 0}), encoding="utf-8")


def test_scan_creates_daily_brief(tmp_path, monkeypatch):
    reports_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    _write_eod(reports_dir, "2026-05-21", ["AAPL", "TSLA"])

    bridge_module.scan_and_process()

    task_files = list(tasks_dir.glob("*.md"))
    assert len(task_files) == 1
    content = task_files[0].read_text(encoding="utf-8")
    assert "stock_research_pod" in content
    assert "AAPL" in content


def test_scan_skips_already_processed(tmp_path, monkeypatch):
    reports_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    _write_eod(reports_dir, "2026-05-21", ["AAPL"])

    bridge_module.scan_and_process()
    bridge_module.scan_and_process()  # second run must not duplicate

    assert len(list(tasks_dir.glob("*.md"))) == 1


def test_scan_handles_multiple_dates(tmp_path, monkeypatch):
    reports_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    for i in range(3):
        _write_eod(reports_dir, f"2026-05-2{i+1}", ["AAPL"])

    bridge_module.scan_and_process()
    assert len(list(tasks_dir.glob("*.md"))) == 3
