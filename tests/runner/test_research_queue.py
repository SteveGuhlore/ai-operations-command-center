import json

import pytest

from runner.ledger import research_queue as rq


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(rq, "QUEUE_FILE", tmp_path / "research-queue.json")
    monkeypatch.setattr(rq, "VERDICTS_FILE", tmp_path / "verdicts.json")
    yield


def _cands():
    return [
        {"symbol": "AAA", "thesis_ref": "vault/tickers/AAA.md", "score": 92, "confidence": "high",
         "proposed_target": 120.0, "proposed_stop": 90.0, "source": "deepdive"},
        {"symbol": "BBB", "thesis_ref": "vault/tickers/BBB.md", "score": 70, "confidence": "medium",
         "proposed_target": 55.0, "proposed_stop": 45.0, "source": "idea_hunt"},
    ]


def test_write_queue_sorts_and_stamps():
    rq.write_queue([_cands()[1], _cands()[0]], target_open="2026-06-08")
    data = json.load(open(rq.QUEUE_FILE))
    assert data["target_open"] == "2026-06-08"
    assert "generated_at" in data
    syms = [c["symbol"] for c in data["candidates"]]
    assert syms == ["AAA", "BBB"]  # sorted best-first by score
    assert all("generated_at" in c for c in data["candidates"])


def test_recheck_validates_against_fresh_price():
    rq.write_queue(_cands(), target_open="2026-06-08")
    # AAA: fresh price 100 is inside [90,120] -> setup holds -> verdict.
    # BBB: fresh price 44 has already breached the stop (45) -> discarded.
    prices = {"AAA": 100.0, "BBB": 44.0}
    res = rq.recheck_queue(price_fn=lambda s: prices.get(s), top_n=5)
    assert res["validated"] == ["AAA"]
    assert res["discarded"] == ["BBB"]
    verdicts = json.load(open(rq.VERDICTS_FILE))
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v["symbol"] == "AAA" and v["verdict"] == "override"
    assert v["target"] == 120.0 and v["stop"] == 90.0
    assert v["confidence"] == "high"


def test_recheck_never_uses_stale_queue_price():
    # A candidate carries no live price (price_fn returns None) -> must be discarded, never
    # executed on the stale proposed levels.
    rq.write_queue([_cands()[0]], target_open="2026-06-08")
    res = rq.recheck_queue(price_fn=lambda s: None, top_n=5)
    assert res["validated"] == [] and res["discarded"] == ["AAA"]
    assert not rq.VERDICTS_FILE.exists()  # nothing executed on the stale proposed levels


def test_recheck_discards_price_above_target():
    rq.write_queue([_cands()[0]], target_open="2026-06-08")
    # price 130 already blew past target 120 -> setup no longer holds
    res = rq.recheck_queue(price_fn=lambda s: 130.0, top_n=5)
    assert res["validated"] == [] and res["discarded"] == ["AAA"]


def test_recheck_respects_top_n():
    rq.write_queue(_cands(), target_open="2026-06-08")
    res = rq.recheck_queue(price_fn=lambda s: {"AAA": 100.0, "BBB": 50.0}.get(s), top_n=1)
    # only the single best candidate is re-checked
    assert res["validated"] == ["AAA"]
    assert "BBB" not in res["validated"] and "BBB" not in res["discarded"]


def test_recheck_appends_to_existing_verdicts():
    (rq.VERDICTS_FILE).write_text(json.dumps(
        [{"date": "2026-06-08", "symbol": "ZZZ", "verdict": "reaffirm"}]))
    rq.write_queue([_cands()[0]], target_open="2026-06-08")
    rq.recheck_queue(price_fn=lambda s: 100.0, top_n=5)
    verdicts = json.load(open(rq.VERDICTS_FILE))
    assert {v["symbol"] for v in verdicts} == {"ZZZ", "AAA"}


def test_recheck_empty_queue():
    res = rq.recheck_queue(price_fn=lambda s: 100.0, top_n=5)
    assert res["validated"] == [] and res["discarded"] == []
