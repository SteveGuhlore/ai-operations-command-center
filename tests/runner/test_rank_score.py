# tests/runner/test_rank_score.py
import pytest
from runner.tools import opportunity as opp


def _row(slug, composite, pod="—"):
    return {"slug": slug, "composite": composite, "phase": "graded",
            "poc": "promising", "system_fit": "7", "est_rev_mo": "500",
            "status": "graded", "pod": pod, "updated": "2026-05-28"}


def test_earner_outranks_higher_composite(monkeypatch):
    monkeypatch.setattr(opp, "get_pod_revenue",
                        lambda pod: 312.0 if pod == "ai-earner" else 0.0)
    earner = _row("ai-earner", 40.0, pod="ai-earner")
    projection = _row("ai-hype", 95.0, pod="—")
    ranked = sorted([projection, earner], key=opp.rank_score, reverse=True)
    assert ranked[0]["slug"] == "ai-earner"


def test_earners_order_by_revenue(monkeypatch):
    rev = {"a": 100.0, "b": 500.0}
    monkeypatch.setattr(opp, "get_pod_revenue", lambda pod: rev.get(pod, 0.0))
    ranked = sorted([_row("a", 90.0, "a"), _row("b", 10.0, "b")],
                    key=opp.rank_score, reverse=True)
    assert [r["slug"] for r in ranked] == ["b", "a"]


def test_non_earners_order_by_composite(monkeypatch):
    monkeypatch.setattr(opp, "get_pod_revenue", lambda pod: 0.0)
    ranked = sorted([_row("low", 30.0), _row("high", 80.0)],
                    key=opp.rank_score, reverse=True)
    assert [r["slug"] for r in ranked] == ["high", "low"]
