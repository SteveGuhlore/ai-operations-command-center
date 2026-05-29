import json
from datetime import date, timedelta

import pytest

from runner.ledger import runway as rw


def _patch(monkeypatch, tmp_path, revenue=0.0, spend=0.0):
    monkeypatch.setattr(rw, "RUNWAY_FILE", tmp_path / "runway.json")
    monkeypatch.setattr(rw, "_real_revenue", lambda: revenue)
    monkeypatch.setattr(rw, "_pod_spend", lambda: spend)


def _write(tmp_path, **over):
    state = {"started_at": date.today().isoformat()}
    state.update(over)
    (tmp_path / "runway.json").write_text(json.dumps(state), encoding="utf-8")


def test_default_state_is_alive_with_grace(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    s = rw.compute_runway()
    assert s["status"] == "alive"
    assert s["expired"] is False
    assert s["days_remaining"] >= 13  # ~14d base grace


def test_budget_expiry_with_no_revenue(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path, revenue=0.0, spend=25.0)  # spend > $20 allowance
    _write(tmp_path, spend_allowance_usd=20.0)
    assert rw.runway_expired() is True


def test_real_revenue_extends_budget(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path, revenue=10.0, spend=25.0)  # allowance 20 + $10 = 30
    _write(tmp_path, spend_allowance_usd=20.0, usd_per_real_dollar=1.0)
    assert rw.runway_expired() is False


def test_time_expiry_with_no_revenue(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path, revenue=0.0, spend=0.0)
    _write(tmp_path, started_at=(date.today() - timedelta(days=20)).isoformat(),
           base_grace_days=14)
    assert rw.runway_expired() is True


def test_real_revenue_extends_time(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path, revenue=10.0, spend=0.0)  # +10 days
    _write(tmp_path, started_at=(date.today() - timedelta(days=20)).isoformat(),
           base_grace_days=14, days_per_real_dollar=1.0)  # deadline = start+24 = today+4
    assert rw.runway_expired() is False


def test_pause_and_revive(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rw.pause_pod()
    assert rw.compute_runway()["status"] == "paused"
    assert rw.runway_expired() is True  # paused stays expired regardless of clock
    rw.pause_pod()  # idempotent
    out = rw.revive()
    assert out["status"] == "alive"
    assert out["revived_count"] == 1
    assert rw.runway_expired() is False


def test_corrupt_file_defaults_alive(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    (tmp_path / "runway.json").write_text("{ not json", encoding="utf-8")
    assert rw.runway_expired() is False
    assert rw.compute_runway()["status"] == "alive"
