# tests/runner/test_revenue_tool.py
import pytest
from runner.tools import revenue_tool as rt
from runner.ledger import revenue as rev


def _patch(monkeypatch, tmp_path):
    monkeypatch.setattr(rev, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(rev, "REVENUE_FILE", tmp_path / "revenue.json")
    monkeypatch.setattr(rt, "REVENUE_MD", tmp_path / "ledger.md")


def test_log_revenue_writes_md_and_mirror(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    out = rt.log_revenue("ai-x", 49.0, source="stripe", external_id="ch_1", note="Pro plan")
    assert out["success"] is True
    md = (tmp_path / "ledger.md").read_text()
    assert "| ai-x | 49.0 | sale | stripe | ch_1 | Pro plan |" in md
    assert rev.get_pod_revenue("ai-x") == pytest.approx(49.0)


def test_log_revenue_dedup_does_not_append_md(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rt.log_revenue("ai-x", 49.0, source="stripe", external_id="ch_1")
    rt.log_revenue("ai-x", 49.0, source="stripe", external_id="ch_1")
    md_rows = [l for l in (tmp_path / "ledger.md").read_text().splitlines()
               if "ch_1" in l]
    assert len(md_rows) == 1


def test_log_revenue_rejects_bad_amount(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    out = rt.log_revenue("ai-x", "not-a-number", source="manual", external_id="")
    assert "error" in out
