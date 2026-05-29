# tests/runner/test_revenue.py
import json
import pytest
from runner.ledger import revenue as rev


def _patch(monkeypatch, tmp_path):
    monkeypatch.setattr(rev, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(rev, "REVENUE_FILE", tmp_path / "revenue.json")


def test_record_revenue_creates_file(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rev.record_revenue("ai-x", 49.00, "stripe", "ch_1")
    data = json.loads((tmp_path / "revenue.json").read_text())
    assert data["total_usd"] == pytest.approx(49.00)
    assert data["by_pod"]["ai-x"] == pytest.approx(49.00)
    assert "ch_1" in data["seen_external_ids"]


def test_record_revenue_dedups_external_id(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    assert rev.record_revenue("ai-x", 49.00, "stripe", "ch_1")["recorded"] is True
    second = rev.record_revenue("ai-x", 49.00, "stripe", "ch_1")
    assert second["recorded"] is False
    assert rev.get_pod_revenue("ai-x") == pytest.approx(49.00)


def test_reversing_row_reduces_total(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rev.record_revenue("ai-x", 49.00, "stripe", "ch_1")
    rev.record_revenue("ai-x", -49.00, "stripe", "re_1", kind="refund")
    assert rev.get_pod_revenue("ai-x") == pytest.approx(0.0)
    assert rev.get_revenue_total() == pytest.approx(0.0)


def test_manual_entry_skips_dedup(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rev.record_revenue("ai-x", 10.0, "manual", "", kind="manual")
    rev.record_revenue("ai-x", 10.0, "manual", "", kind="manual")
    assert rev.get_pod_revenue("ai-x") == pytest.approx(20.0)


def test_does_not_reset_daily(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    (tmp_path / "revenue.json").write_text(json.dumps(
        {"by_pod": {"ai-x": 100.0}, "total_usd": 100.0, "seen_external_ids": []}))
    assert rev.get_pod_revenue("ai-x") == pytest.approx(100.0)
