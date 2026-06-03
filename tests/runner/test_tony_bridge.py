import json
from runner.bridge import tony_bridge as bridge_module


def _setup(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    bridge_dir = tmp_path / "bridge" / "tony-stocks"
    tasks_dir = tmp_path / "workspace" / "tasks" / "todo"
    reports_dir.mkdir(parents=True)
    bridge_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)
    monkeypatch.setattr(bridge_module, "TRADING_REPORTS_DIR", reports_dir)
    monkeypatch.setattr(bridge_module, "BRIDGE_MD_DIR", bridge_dir)
    monkeypatch.setattr(bridge_module, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(bridge_module, "_PROCESSED_LOG", tmp_path / "processed.json")
    monkeypatch.setattr(bridge_module, "VAULT_DIR", tmp_path / "vault")
    return reports_dir, bridge_dir, tasks_dir


def _write_eod(reports_dir, date_str, tickers):
    d = reports_dir / date_str
    d.mkdir(parents=True, exist_ok=True)
    (d / "eod_report.json").write_text(
        json.dumps({"active_symbols": tickers, "weakening": 0}), encoding="utf-8")


def _write_bridge(bridge_dir, date_str, body):
    (bridge_dir / f"{date_str}.md").write_text(
        f"---\ndate: {date_str}\nsource: TradingBotAgentProject\nexport_type: eod-bridge\n---\n\n{body}\n",
        encoding="utf-8",
    )


def test_scan_creates_daily_brief(tmp_path, monkeypatch):
    reports_dir, _bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    _write_eod(reports_dir, "2026-05-21", ["AAPL", "TSLA"])

    bridge_module.scan_and_process()

    task_files = list(tasks_dir.glob("*.md"))
    assert len(task_files) == 1
    content = task_files[0].read_text(encoding="utf-8")
    assert "stock_research_pod" in content
    assert "AAPL" in content


def test_scan_skips_already_processed(tmp_path, monkeypatch):
    reports_dir, _bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    _write_eod(reports_dir, "2026-05-21", ["AAPL"])

    bridge_module.scan_and_process()
    bridge_module.scan_and_process()  # second run must not duplicate

    assert len(list(tasks_dir.glob("*.md"))) == 1


def test_scan_handles_multiple_dates(tmp_path, monkeypatch):
    reports_dir, _bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    for i in range(3):
        _write_eod(reports_dir, f"2026-05-2{i+1}", ["AAPL"])

    bridge_module.scan_and_process()
    assert len(list(tasks_dir.glob("*.md"))) == 3


def test_scan_ingests_markdown_bridge(tmp_path, monkeypatch):
    _reports_dir, bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    _write_bridge(bridge_dir, "2026-05-29", "## Tier 1\n### [[ZETA]]\nScore 88.75")

    bridge_module.scan_and_process()

    task_files = list(tasks_dir.glob("*.md"))
    assert len(task_files) == 1
    content = task_files[0].read_text(encoding="utf-8")
    assert "TONY-DAILY-BRIEF-20260529" in content
    assert "ZETA" in content
    assert "market_research_worker" in content


def test_vault_history_filters_poison(tmp_path, monkeypatch):
    sessions = tmp_path / "vault" / "sessions" / "2026-06-03"
    sessions.mkdir(parents=True)
    (sessions / "TONY-A.md").write_text(
        "AMD CLOSE — scanner data integrity failure detected.", encoding="utf-8")
    (sessions / "TONY-B.md").write_text(
        "DAL reaffirm — strong breakout, tony_score 80.", encoding="utf-8")
    monkeypatch.setattr(bridge_module, "VAULT_DIR", tmp_path / "vault")
    out = bridge_module._load_vault_history()
    assert "DAL reaffirm" in out and "integrity failure" not in out


def test_intraday_bridges_each_fire(tmp_path, monkeypatch):
    _reports_dir, bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    for slot in ("2026-06-03T1030", "2026-06-03T1300", "2026-06-03-eod"):
        (bridge_dir / f"{slot}.md").write_text(
            "---\ndate: 2026-06-03\n---\n\n## Tier 1\n### [[ZETA]]\n", encoding="utf-8")
    bridge_module.scan_and_process()
    names = [p.name for p in tasks_dir.glob("*.md")]
    assert len(names) == 3  # each intraday slot fires its own run
    assert any("TONY-INTRADAY-20260603-1030" in n for n in names)
    assert any("TONY-INTRADAY-20260603-1300" in n for n in names)
    # intraday tasks are the LIGHT variant, not the heavy deep-dive
    body = (tasks_dir / "TONY-INTRADAY-20260603-1030.md").read_text(encoding="utf-8")
    assert "market_scan_intraday" in body and "LIGHT intraday update" in body
    assert "for EACH Tier 1 ticker" not in body  # the heavy daily workflow must be absent


def test_daily_bridge_is_full_not_intraday(tmp_path, monkeypatch):
    _reports_dir, bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    _write_bridge(bridge_dir, "2026-06-03", "## Tier 1\n### [[ZETA]]\nScore 88")
    bridge_module.scan_and_process()
    body = (tasks_dir / "TONY-DAILY-BRIEF-20260603.md").read_text(encoding="utf-8")
    assert "for EACH Tier 1 ticker" in body  # pure-date stays the full deep-dive


def test_intraday_bridge_not_duplicated(tmp_path, monkeypatch):
    _reports_dir, bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    (bridge_dir / "2026-06-03-1030.md").write_text(
        "---\ndate: 2026-06-03\n---\n\n## Tier 1\n### [[ZETA]]\n", encoding="utf-8")
    bridge_module.scan_and_process()
    bridge_module.scan_and_process()
    assert len(list(tasks_dir.glob("*.md"))) == 1


def test_markdown_bridge_not_duplicated(tmp_path, monkeypatch):
    _reports_dir, bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    _write_bridge(bridge_dir, "2026-05-29", "## Tier 1\n### [[ZETA]]")

    bridge_module.scan_and_process()
    bridge_module.scan_and_process()

    assert len(list(tasks_dir.glob("*.md"))) == 1


def test_fanout_spawns_per_ticker(tmp_path, monkeypatch):
    _reports_dir, bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(bridge_module, "FANOUT_MIN_TIER1", 2)
    body = ("## Tier 1\n### [[AAA]]\n- Days active: 3\n### [[BBB]]\n- Days active: 4\n"
            "## Tier 2\n### [[CCC]]\n## For Tony\nx")
    _write_bridge(bridge_dir, "2026-06-03", body)
    bridge_module.scan_and_process()
    names = [p.name for p in tasks_dir.glob("*.md")]
    assert any("TONY-TKR-AAA" in n for n in names)
    assert any("TONY-TKR-BBB" in n for n in names)
    assert not any("CCC" in n for n in names)  # Tier 2 excluded


def test_fanout_off_by_default(tmp_path, monkeypatch):
    _reports_dir, bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(bridge_module, "FANOUT_MIN_TIER1", 0)
    body = "## Tier 1\n### [[AAA]]\n### [[BBB]]\n## For Tony\nx"
    _write_bridge(bridge_dir, "2026-06-03", body)
    bridge_module.scan_and_process()
    assert not any("TONY-TKR" in p.name for p in tasks_dir.glob("*.md"))


def test_markdown_wins_when_both_sources_present(tmp_path, monkeypatch):
    reports_dir, bridge_dir, tasks_dir = _setup(tmp_path, monkeypatch)
    _write_eod(reports_dir, "2026-05-29", ["AAPL"])
    _write_bridge(bridge_dir, "2026-05-29", "## Tier 1\n### [[ZETA]]")

    bridge_module.scan_and_process()

    task_files = list(tasks_dir.glob("*.md"))
    assert len(task_files) == 1  # shared dedup key — same date never double-fires
    assert "ZETA" in task_files[0].read_text(encoding="utf-8")
