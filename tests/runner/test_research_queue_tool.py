"""queue_research_candidate — deterministic research-queue persistence (replaces the LLM
hand-writing research-queue.json, which left it empty and triggered the Scout/Forge loop)."""
import importlib
import os

import pytest


@pytest.fixture
def rq(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_RESEARCH_QUEUE_FILE", str(tmp_path / "rq.json"))
    from runner.ledger import research_queue as mod
    importlib.reload(mod)
    monkeypatch.setattr(mod, "_next_open_date_unavailable", False, raising=False)
    return mod


def test_appends_and_ranks_best_first(rq):
    rq.queue_research_candidate("ZETA", 70, "medium", 30.0, 26.0)
    rq.queue_research_candidate("GTLB", 88, "high", 78.5, 71.0, "momentum", "deepdive")
    q = rq.read_queue()
    assert [c["symbol"] for c in q["candidates"]] == ["GTLB", "ZETA"]  # ranked by score desc
    assert q["candidates"][0]["proposed_target"] == 78.5
    assert q["target_open"]  # header stamped


def test_dedupes_by_symbol_latest_wins(rq):
    rq.queue_research_candidate("AAA", 60)
    rq.queue_research_candidate("aaa", 90)  # case-insensitive replace
    q = rq.read_queue()
    assert len(q["candidates"]) == 1 and q["candidates"][0]["score"] == 90.0


def test_rejects_missing_symbol_and_bad_score(rq):
    assert "error" in rq.queue_research_candidate("", 80)
    assert "error" in rq.queue_research_candidate("AAA", "not-a-number")
    assert rq.read_queue()["candidates"] == []  # nothing persisted from rejected calls


def test_coerces_numeric_strings(rq):
    res = rq.queue_research_candidate("BBB", "82", proposed_target="40", proposed_stop="35")
    assert res["success"]
    c = rq.read_queue()["candidates"][0]
    assert c["score"] == 82.0 and c["proposed_target"] == 40.0 and c["proposed_stop"] == 35.0


def test_new_open_resets_queue_and_advances_target(rq, monkeypatch):
    import runner.bridge.research_wave as rw
    # day 1: queue targets the first open
    monkeypatch.setattr(rw, "_next_open_date", lambda *a, **k: "2026-06-10")
    rq.queue_research_candidate("OLD1", 70)
    rq.queue_research_candidate("OLD2", 72)
    assert rq.read_queue()["target_open"] == "2026-06-10"
    # day 2: a new open must reset the queue (drop stale names) and ADVANCE target_open,
    # not freeze it at 2026-06-10
    monkeypatch.setattr(rw, "_next_open_date", lambda *a, **k: "2026-06-11")
    rq.queue_research_candidate("NEW1", 85)
    q = rq.read_queue()
    assert q["target_open"] == "2026-06-11"
    assert [c["symbol"] for c in q["candidates"]] == ["NEW1"]  # OLD1/OLD2 dropped


def test_tool_spec_shape(rq):
    assert rq.TOOL_SPEC["name"] == "queue_research_candidate"
    assert set(rq.TOOL_SPEC["input_schema"]["required"]) == {"symbol", "score"}
