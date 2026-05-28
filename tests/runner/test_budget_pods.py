# tests/runner/test_budget_pods.py
import importlib


def _fresh_budget(tmp_path, monkeypatch):
    import runner.ledger.budget as budget
    importlib.reload(budget)
    monkeypatch.setattr(budget, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(budget, "SPEND_FILE", tmp_path / "daily-spend.json")
    return budget


def test_record_spend_tracks_pod(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    budget.record_spend("opportunity_worker", 1.5, pod="opportunity_pod")
    budget.record_spend("heavy_worker", 0.5, pod="opportunity_pod")
    assert budget.get_pod_spend("opportunity_pod") == 2.0


def test_record_spend_without_pod_is_safe(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    budget.record_spend("outreach_worker", 0.25)
    assert budget.get_pod_spend("opportunity_pod") == 0.0
    assert budget.get_daily_spend() == 0.25


def test_pod_budget_exceeded(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    monkeypatch.setattr(budget, "get_pod_cap", lambda pod: 10.0)
    budget.record_spend("opportunity_worker", 9.99, pod="opportunity_pod")
    assert budget.is_pod_budget_exceeded("opportunity_pod") is False
    budget.record_spend("opportunity_worker", 0.02, pod="opportunity_pod")
    assert budget.is_pod_budget_exceeded("opportunity_pod") is True
