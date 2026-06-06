# tests/runner/test_budget.py
import json
import pytest
from datetime import date
from pathlib import Path
from runner.ledger import budget as budget_module


def _patch_budget(monkeypatch, tmp_path, cap: float = 50.0):
    monkeypatch.setattr(budget_module, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(budget_module, "SPEND_FILE", tmp_path / "daily-spend.json")
    monkeypatch.setattr(
        budget_module,
        "get_daily_cap",
        lambda: cap,
    )


def test_record_spend_creates_file(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path)
    budget_module.record_spend("debug_worker", 0.05)
    data = json.loads((tmp_path / "daily-spend.json").read_text())
    assert data["total_usd"] == pytest.approx(0.05)
    assert data["by_role"]["debug_worker"] == pytest.approx(0.05)


def test_record_spend_accumulates(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path)
    budget_module.record_spend("debug_worker", 0.05)
    budget_module.record_spend("debug_worker", 0.10)
    assert budget_module.get_daily_spend() == pytest.approx(0.15)


def test_is_budget_exceeded_false_under_cap(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path, cap=50.0)
    budget_module.record_spend("manager", 5.00)
    assert budget_module.is_budget_exceeded() is False


def test_is_budget_exceeded_true_at_cap(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path, cap=5.00)
    budget_module.record_spend("manager", 5.00)
    assert budget_module.is_budget_exceeded() is True


def test_offhours_lane_runs_past_daytime_cap(tmp_path, monkeypatch):
    # daytime cap $5 is blown, but the off-hours lane (uncapped by default) still runs.
    _patch_budget(monkeypatch, tmp_path, cap=5.00)
    monkeypatch.delenv("TONY_OFFHOURS_BUDGET_USD", raising=False)
    budget_module.record_spend("market_research_worker", 50.00)
    assert budget_module.is_budget_exceeded() is True              # daytime cap enforced
    assert budget_module.is_budget_exceeded(off_hours=True) is False  # off-hours lane uncapped


def test_offhours_lane_can_be_bounded(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path, cap=5.00)
    monkeypatch.setenv("TONY_OFFHOURS_BUDGET_USD", "20")
    budget_module.record_spend("market_research_worker", 25.00)
    assert budget_module.is_budget_exceeded(off_hours=True) is True


def test_daytime_cap_unchanged(tmp_path, monkeypatch):
    # regression: the no-arg call is byte-for-byte today's behavior.
    _patch_budget(monkeypatch, tmp_path, cap=10.00)
    budget_module.record_spend("manager", 9.99)
    assert budget_module.is_budget_exceeded() is False
    budget_module.record_spend("manager", 0.01)
    assert budget_module.is_budget_exceeded() is True


def test_spend_resets_on_new_day(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path)
    spend_file = tmp_path / "daily-spend.json"
    # Write yesterday's data
    spend_file.write_text(json.dumps({
        "date": "2000-01-01",
        "total_usd": 999.0,
        "by_role": {}
    }))
    assert budget_module.get_daily_spend() == pytest.approx(0.0)
