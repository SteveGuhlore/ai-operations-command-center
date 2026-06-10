import json

import pytest

from runner.ledger import tony_realized as tr


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "REALIZED_FILE", tmp_path / "tony-realized.json")
    yield


def _fill(sym, side, qty, price, oid, otype="market", t="2026-06-05T13:00:00Z"):
    return {"symbol": sym, "side": side, "qty": qty, "price": price, "order_id": oid,
            "order_type": otype, "time": t, "date": t[:10]}


def test_records_returns_rows_newest_first(tmp_path, monkeypatch):
    f = tmp_path / "tony-realized.json"
    monkeypatch.setattr(tr, "REALIZED_FILE", f)
    f.write_text(json.dumps([
        {"symbol": "AAA", "realized_pl": 10, "reason": "target", "date": "2026-06-01"},
        {"symbol": "BBB", "realized_pl": -5, "reason": "stop", "date": "2026-06-05"},
    ]), encoding="utf-8")
    rows = tr.records()
    assert [r["symbol"] for r in rows] == ["BBB", "AAA"]   # newest first by date
    assert tr.records(newest_first=False)[0]["symbol"] == "AAA"


def test_fifo_matches_sell_to_prior_buy_with_real_pl():
    fills = [
        _fill("FCX", "buy", 14, 70.15, "b1", t="2026-06-04T19:33:00Z"),
        _fill("FCX", "sell", 14, 65.85, "s1", "stop", t="2026-06-05T13:41:00Z"),
    ]
    rows = tr.reconcile_from_fills(fills)
    assert len(rows) == 1
    r = rows[0]
    assert r["symbol"] == "FCX" and r["reason"] == "stop"
    assert r["entry"] == 70.15 and r["exit"] == 65.85
    assert r["realized_pl"] == round((65.85 - 70.15) * 14, 2)  # -60.2
    assert r["exit_order_id"] == "s1"


def test_sell_without_matching_buy_is_skipped_not_invented():
    rows = tr.reconcile_from_fills([_fill("SLB", "sell", 17, 54.49, "s2", "stop")])
    assert rows == []  # never fabricate an entry


def test_order_type_maps_reason():
    fills = [_fill("X", "buy", 1, 10, "b"), _fill("X", "sell", 1, 12, "s", "limit")]
    assert tr.reconcile_from_fills(fills)[0]["reason"] == "target"


def test_partial_fifo_across_two_lots():
    fills = [
        _fill("Q", "buy", 10, 5.0, "b1", t="2026-06-01T10:00:00Z"),
        _fill("Q", "buy", 10, 7.0, "b2", t="2026-06-02T10:00:00Z"),
        _fill("Q", "sell", 15, 8.0, "s1", "stop", t="2026-06-03T10:00:00Z"),
    ]
    r = tr.reconcile_from_fills(fills)[0]
    assert r["qty"] == 15
    # 10 @5 + 5 @7 = 85 cost over 15 -> avg 5.6667; pl = (8-5.6667)*15
    assert r["entry"] == round(85 / 15, 4)
    assert r["realized_pl"] == round((8.0 - 85 / 15) * 15, 2)
    assert r["reason"] == "trim"   # sold 15 of 20 -> 5 still held -> a TRIM, not a close


def test_full_exit_is_not_a_trim_and_agg_splits_them():
    fills = [
        _fill("F", "buy", 10, 100.0, "b1", t="2026-06-01T10:00:00Z"),
        _fill("F", "sell", 6, 110.0, "s1", "market", t="2026-06-02T10:00:00Z"),   # trim (4 left)
        _fill("F", "sell", 4, 120.0, "s2", "market", t="2026-06-03T10:00:00Z"),   # close (0 left)
    ]
    rows = tr.reconcile_from_fills(fills)
    assert [r["reason"] for r in rows] == ["trim", "close"]
    agg = tr._agg(rows)
    assert agg["count"] == 1 and agg["trims"] == 1          # one CLOSED trade, one trim
    assert agg["wins"] == 1 and agg["losses"] == 0          # win/loss over closes only
    assert agg["closed_pl"] == round((120 - 100) * 4, 2)    # close P/L only
    assert agg["trim_pl"] == round((110 - 100) * 6, 2)      # trim P/L separate
    assert agg["realized_pl"] == round(agg["closed_pl"] + agg["trim_pl"], 2)  # total = real $


def test_rebuild_drops_bogus_unid_rows_and_dedups():
    tr.REALIZED_FILE.write_text(json.dumps([
        {"symbol": "HELD", "reason": "unknown", "realized_pl": 0.0},          # legacy bogus, no id
        {"symbol": "OLD", "realized_pl": 5.0, "exit_order_id": "keep1", "date": "2026-05-01"},
    ]), encoding="utf-8")
    fills = [_fill("FCX", "buy", 14, 70.15, "b1", t="2026-06-04T19:33:00Z"),
             _fill("FCX", "sell", 14, 65.85, "s1", "stop", t="2026-06-05T13:41:00Z")]
    res = tr.rebuild_from_fills(fills)
    rows = json.loads(tr.REALIZED_FILE.read_text(encoding="utf-8"))
    syms = {r["symbol"] for r in rows}
    assert "HELD" not in syms          # bogus dropped
    assert "OLD" in syms and "FCX" in syms  # id'd history kept + new exit added
    # re-running must not duplicate the same exit
    tr.rebuild_from_fills(fills)
    rows2 = json.loads(tr.REALIZED_FILE.read_text(encoding="utf-8"))
    assert len(rows2) == len(rows)


def test_rebuild_reconciled_rows_override_stale_labels():
    # a stored row mislabeled 'close' must be UPDATED when re-derivation says 'trim' —
    # the first repair attempt failed because existing rows shadowed the reconciled ones
    tr.REALIZED_FILE.write_text(json.dumps([
        {"symbol": "HAL", "realized_pl": 187.33, "reason": "close",
         "exit_order_id": "s1", "date": "2026-06-10"},
    ]), encoding="utf-8")
    fills = [
        _fill("HAL", "buy", 753, 40.0, "b1", t="2026-06-09T10:00:00Z"),
        _fill("HAL", "sell", 505, 40.28, "s1", "market", t="2026-06-10T14:33:00Z"),  # 248 still held
    ]
    tr.rebuild_from_fills(fills)
    rows = json.loads(tr.REALIZED_FILE.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["reason"] == "trim"   # re-derived label wins over the stale stored one
