# tests/runner/test_daily_jobs.py
import importlib
from datetime import datetime, timedelta


def _fresh(tmp_path, monkeypatch):
    import runner.scheduler.daily_jobs as dj
    importlib.reload(dj)
    monkeypatch.setattr(dj, "STATE_FILE", tmp_path / "scheduler-state.json")
    return dj


def test_scout_due_when_never_run(tmp_path, monkeypatch):
    dj = _fresh(tmp_path, monkeypatch)
    assert dj.scout_due(interval_hours=2) is True


def test_scout_not_due_within_interval(tmp_path, monkeypatch):
    dj = _fresh(tmp_path, monkeypatch)
    dj.mark_scout_ran()
    assert dj.scout_due(interval_hours=2) is False


def test_scout_due_after_interval(tmp_path, monkeypatch):
    dj = _fresh(tmp_path, monkeypatch)
    dj.mark_scout_ran()
    old = (datetime.now() - timedelta(hours=3)).isoformat()
    dj._write({"last_scout": old})
    assert dj.scout_due(interval_hours=2) is True


def test_daily_learning_runs_once_per_day(tmp_path, monkeypatch):
    dj = _fresh(tmp_path, monkeypatch)
    if dj.datetime.now().hour < 2:
        return  # before 2am the gate is intentionally closed; skip
    assert dj.daily_learning_due(hour_after=2) is True
    dj.mark_learning_ran()
    assert dj.daily_learning_due(hour_after=2) is False
