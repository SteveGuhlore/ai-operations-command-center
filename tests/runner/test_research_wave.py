import datetime as dt
import json

import pytest

from runner.bridge import research_wave as rw
from runner.ledger import market_clock as mc

ET = mc._ET


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(rw, "TASKS_DIR", tmp_path / "todo")
    monkeypatch.setattr(rw, "STATE_FILE", tmp_path / "research-wave-state.json")
    bd = tmp_path / "bridge"; bd.mkdir()
    monkeypatch.setattr(rw, "BRIDGE_MD_DIR", bd)
    (bd / "2026-06-05.md").write_text(
        "## Tier 1\n"
        "### [[AAA]]\n- Days active: 4 | Score: 90 | Target: $30 | Stop: $25\n"
        "### [[BBB]]\n- Days active: 3 | Score: 80 | Target: $40 | Stop: $35\n"
        "## Tier 2\n"
        "| Ticker | Score | Setup | Close | x | y | R/R |\n"
        "| [[CCC]] | 70 | breakout | $10 | | | 2.0 |\n"
        "## Tier 3\n"
        "| Ticker | Score | Setup | Close | x | y | R/R |\n"
        "| [[DDD]] | 60 | base | $5 | | | 1.5 |\n"
    )
    yield


def _open_date():
    # next weekday open for a known closed Saturday
    return rw._next_open_date(dt.datetime(2026, 6, 6, 18, 0, tzinfo=ET))


def test_next_open_date_skips_weekend_and_holiday():
    # Saturday 2026-06-06 -> Monday 2026-06-08
    assert rw._next_open_date(dt.datetime(2026, 6, 6, 18, 0, tzinfo=ET)) == "2026-06-08"
    # Thursday 2026-06-18 evening -> Friday is Juneteenth -> Monday 2026-06-22
    assert rw._next_open_date(dt.datetime(2026, 6, 18, 18, 0, tzinfo=ET)) == "2026-06-22"
    # weeknight Tuesday 2026-06-09 evening -> Wednesday 2026-06-10
    assert rw._next_open_date(dt.datetime(2026, 6, 9, 18, 0, tzinfo=ET)) == "2026-06-10"


def test_universe_symbols_full_tiers():
    syms = rw._universe_symbols()
    assert set(syms) == {"AAA", "BBB", "CCC", "DDD"}


def test_wave_enqueues_once_and_dedups(monkeypatch):
    monkeypatch.setenv("TONY_MARKET_SESSION", "closed")
    res1 = rw.maybe_stage_research_wave(now=dt.datetime(2026, 6, 6, 18, 0, tzinfo=ET))
    assert res1["staged"] is True
    files = list((rw.TASKS_DIR).glob("*.md"))
    # one deep-dive per universe symbol + the 6 fixed wave tasks
    types = {}
    for f in files:
        txt = f.read_text(encoding="utf-8")
        for line in txt.splitlines():
            if line.startswith("task_type:"):
                t = line.split(":", 1)[1].strip()
                types[t] = types.get(t, 0) + 1
        assert "assigned_agent: market_research_worker" in txt
        assert "pod: stock_research_pod" in txt
    assert types.get("ticker_deepdive") == 4
    for t in ("tony_macro_synthesis", "tony_catalyst_scan", "tony_idea_hunt",
              "tony_book_stresstest", "tony_self_review", "tony_research_rank"):
        assert types.get(t) == 1
    # re-entering the same closed window must NOT double-enqueue
    res2 = rw.maybe_stage_research_wave(now=dt.datetime(2026, 6, 6, 20, 0, tzinfo=ET))
    assert res2["staged"] is False
    assert len(list(rw.TASKS_DIR.glob("*.md"))) == len(files)


def test_no_wave_when_market_open(monkeypatch):
    monkeypatch.setenv("TONY_MARKET_SESSION", "open")
    res = rw.maybe_stage_research_wave(now=dt.datetime(2026, 6, 9, 11, 0, tzinfo=ET))
    assert res["staged"] is False
    assert res["reason"] == "market_open"
    assert list(rw.TASKS_DIR.glob("*.md")) == []


def test_state_keyed_by_open_date(monkeypatch):
    monkeypatch.setenv("TONY_MARKET_SESSION", "closed")
    rw.maybe_stage_research_wave(now=dt.datetime(2026, 6, 6, 18, 0, tzinfo=ET))
    state = json.load(open(rw.STATE_FILE))
    assert state.get("staged_for") == "2026-06-08"
