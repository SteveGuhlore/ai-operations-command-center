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
