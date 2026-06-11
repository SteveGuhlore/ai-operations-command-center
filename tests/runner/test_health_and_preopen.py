"""Health-monitor issue detection + the pre-open / alert scheduler markers (the post-incident
safeguards: backlog + oversize warnings, and a cron-independent pre-open backstop)."""
from runner.tools import health_monitor as hm


def _pin_today(monkeypatch, day):
    import runner.ledger.market_clock as mc
    monkeypatch.setattr(mc, "trading_day", lambda *a, **k: day)


def test_collect_issues_flags_stale_backlog_and_pyramid(monkeypatch):
    _pin_today(monkeypatch, "2026-06-11")
    monkeypatch.setenv("TONY_OVERSIZE_ALERT_MULT", "1.6")  # ENTRY_NOTIONAL 10k -> threshold 16k
    positions = [
        {"symbol": "AAA", "qty": 200, "avg_entry_price": 100},               # cost basis $20k -> pyramid
        {"symbol": "WIN", "qty": 67,  "avg_entry_price": 100, "current_price": 300},  # cost $6.7k -> winner, fine
    ]
    verdicts = [{"date": "2026-06-10", "symbol": "X"}, {"date": "2026-06-11", "symbol": "Y"}]  # 06-10 is stale
    issues = hm.collect_issues(positions=positions, verdicts=verdicts)
    assert any("backlog" in i.lower() for i in issues)
    assert any("AAA" in i for i in issues)
    assert not any("WIN" in i for i in issues)   # a winner is NOT pyramiding (cost basis, not market value)


def test_collect_issues_single_day_large_is_healthy(monkeypatch):
    # 150 verdicts but all TODAY -> whole-universe deep-dives, NOT a backlog
    _pin_today(monkeypatch, "2026-06-10")
    positions = [{"symbol": "AAA", "qty": 1, "avg_entry_price": 100}]  # $100 -> fine
    verdicts = [{"date": "2026-06-10", "symbol": f"S{i}"} for i in range(150)]
    assert hm.collect_issues(positions=positions, verdicts=verdicts) == []


def test_preopen_and_alert_markers(tmp_path, monkeypatch):
    from runner.scheduler import daily_jobs as dj
    monkeypatch.setattr(dj, "STATE_FILE", tmp_path / "sched.json")
    assert dj.preopen_done_today() is False
    dj.mark_preopen_ran()
    assert dj.preopen_done_today() is True
    assert dj.alert_due("preopen_missing") is True
    dj.mark_alert_ran("preopen_missing")
    assert dj.alert_due("preopen_missing") is False


def test_health_alert_due_throttle(tmp_path, monkeypatch):
    from runner.scheduler import daily_jobs as dj
    monkeypatch.setattr(dj, "STATE_FILE", tmp_path / "sched.json")
    assert dj.health_alert_due(interval_hours=1) is True
    dj.mark_health_check_ran()
    assert dj.health_alert_due(interval_hours=1) is False
