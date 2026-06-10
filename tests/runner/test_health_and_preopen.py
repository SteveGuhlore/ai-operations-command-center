"""Health-monitor issue detection + the pre-open / alert scheduler markers (the post-incident
safeguards: backlog + oversize warnings, and a cron-independent pre-open backstop)."""
from runner.tools import health_monitor as hm


def test_collect_issues_flags_backlog_and_oversize(monkeypatch):
    monkeypatch.setenv("TONY_VERDICT_BACKLOG_ALERT", "50")
    monkeypatch.setenv("TONY_OVERSIZE_ALERT_MULT", "1.6")  # ENTRY_NOTIONAL 10k -> threshold 16k
    positions = [
        {"symbol": "AAA", "qty": 100, "current_price": 300},   # $30k -> oversized
        {"symbol": "BBB", "qty": 10, "current_price": 50},      # $500 -> fine
    ]
    issues = hm.collect_issues(positions=positions, verdict_count=80)
    assert any("backlog" in i.lower() for i in issues)
    assert any("AAA" in i for i in issues)
    assert not any("BBB" in i for i in issues)


def test_collect_issues_healthy_is_empty(monkeypatch):
    monkeypatch.setenv("TONY_VERDICT_BACKLOG_ALERT", "60")
    positions = [{"symbol": "AAA", "qty": 1, "current_price": 100}]  # $100 -> fine
    assert hm.collect_issues(positions=positions, verdict_count=5) == []


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
