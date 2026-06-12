"""Profit ratchet + swing max-hold + never-loosen guard (the per-position lifecycle layer).

Design contract (from the Monte-Carlo stress test of trailing methods):
- the floor arms only after the high-water clears entry + BE_R*R (R = entry - initial stop,
  the scanner's own per-name volatility unit);
- floor = max(entry, hwm - TRAIL_R*R), capped below the live price, raised only — Tony's own
  tighter stop always wins;
- swing positions close at the max-hold cap (default 30d); horizon 'long' is exempt, 'day' is 1d;
- an `adjust` may move the target freely but can never LOOSEN the live stop.
"""
import json

import pytest

from runner.ledger import alpaca_paper as ap
from runner.ledger import position_meta as pm


def _pos(sym="WIN", qty=50, entry=100.0, px=117.0):
    return {"symbol": sym, "qty": qty, "avg_entry_price": entry, "current_price": px}


def _meta(entry=100.0, hwm=117.0, stop=92.0, first_seen="2026-06-01", horizon="swing"):
    return {"entry": entry, "hwm": hwm, "initial_stop": stop,
            "first_seen": first_seen, "horizon": horizon}


# ----------------------------------------------------------------- plan_stop_ratchets

def test_ratchet_arms_after_cushion_and_trails_hwm():
    # R = 100-92 = 8. BE arms at hwm >= 100 + 0.75*8 = 106. hwm 117 -> floor = 117 - 1.25*8 = 107.
    plan = ap.plan_stop_ratchets([_pos()], {"WIN": {"stop": 92.0, "target": 130.0}},
                                 {"WIN": _meta()}, "2026-06-11", set(),
                                 be_r=0.75, trail_r=1.25, min_step_pct=0.5)
    assert len(plan) == 1
    rp = plan[0]
    assert rp["symbol"] == "WIN" and rp["stop"] == 107.0 and rp["target"] == 130.0
    assert rp["stop"] > 100.0  # profit locked above entry


def test_ratchet_does_not_arm_before_cushion():
    # hwm 104 < 106 arm level -> no ratchet (don't choke a fresh position)
    plan = ap.plan_stop_ratchets([_pos(px=104.0)], {"WIN": {"stop": 92.0, "target": 130.0}},
                                 {"WIN": _meta(hwm=104.0)}, "2026-06-11", set(),
                                 be_r=0.75, trail_r=1.25)
    assert plan == []


def test_ratchet_never_lowers_and_respects_tonys_tighter_stop():
    # Tony already moved the stop to 110 — above the 107 floor -> the ratchet stays silent
    plan = ap.plan_stop_ratchets([_pos()], {"WIN": {"stop": 110.0, "target": 130.0}},
                                 {"WIN": _meta()}, "2026-06-11", set(),
                                 be_r=0.75, trail_r=1.25)
    assert plan == []


def test_ratchet_floor_never_below_entry_once_armed():
    # hwm 107 (armed: >=106), trail says 107 - 10 = 97 < entry -> floor clamps to entry (break-even)
    plan = ap.plan_stop_ratchets([_pos(px=106.5)], {"WIN": {"stop": 92.0, "target": 130.0}},
                                 {"WIN": _meta(hwm=107.0)}, "2026-06-11", set(),
                                 be_r=0.75, trail_r=1.25)
    assert len(plan) == 1 and plan[0]["stop"] == 100.0


def test_ratchet_capped_below_live_price():
    # deep retrace: hwm 117 -> px 105; floor 107 would sit ABOVE market -> cap to 0.99*px
    plan = ap.plan_stop_ratchets([_pos(px=105.0)], {"WIN": {"stop": 92.0, "target": 130.0}},
                                 {"WIN": _meta()}, "2026-06-11", set(),
                                 be_r=0.75, trail_r=1.25)
    assert len(plan) == 1 and plan[0]["stop"] == round(105.0 * 0.99, 2)


def test_ratchet_skips_naked_and_unknown_positions():
    # no stop leg -> protection reconcile owns it first; no meta -> not adopted yet
    assert ap.plan_stop_ratchets([_pos()], {"WIN": {"stop": None, "target": 130.0}},
                                 {"WIN": _meta()}, "2026-06-11", set()) == []
    assert ap.plan_stop_ratchets([_pos()], {"WIN": {"stop": 92.0, "target": 130.0}},
                                 {}, "2026-06-11", set()) == []


def test_ratchet_churn_guard_and_done_key():
    legs = {"WIN": {"stop": 106.8, "target": 130.0}}   # floor 107 is <0.5% above 106.8 -> skip
    assert ap.plan_stop_ratchets([_pos()], legs, {"WIN": _meta()}, "2026-06-11", set(),
                                 be_r=0.75, trail_r=1.25, min_step_pct=0.5) == []
    done = {"ratchet:2026-06-11:WIN:107.0"}            # same level already done today -> skip
    assert ap.plan_stop_ratchets([_pos()], {"WIN": {"stop": 92.0, "target": 130.0}},
                                 {"WIN": _meta()}, "2026-06-11", done,
                                 be_r=0.75, trail_r=1.25) == []


def test_ratchet_uses_r_proxy_for_adopted_winner():
    # adopted mid-flight: initial_stop already above entry -> R falls back to 4% of entry (=4.0)
    m = _meta(stop=103.0)   # stop above entry -> entry-stop negative -> proxy
    plan = ap.plan_stop_ratchets([_pos()], {"WIN": {"stop": 103.0, "target": 130.0}},
                                 {"WIN": m}, "2026-06-11", set(), be_r=0.75, trail_r=1.25)
    # R=4 -> arm at 103, hwm 117 -> floor = 117 - 5 = 112 > 103 -> raise
    assert len(plan) == 1 and plan[0]["stop"] == 112.0


# ----------------------------------------------------------------- plan_max_hold_closes

def test_max_hold_closes_swing_at_cap_but_not_before():
    meta = {"OLD": _meta(first_seen="2026-05-12"), "NEW": _meta(first_seen="2026-06-01")}
    positions = [_pos("OLD"), _pos("NEW")]
    plan = ap.plan_max_hold_closes(positions, meta, "2026-06-11", set(), default_days=30)
    assert [c["symbol"] for c in plan] == ["OLD"]      # 30 days -> closed; 10 days -> kept
    assert plan[0]["age_days"] == 30


def test_max_hold_horizons_day_and_long():
    meta = {"DAYT": _meta(first_seen="2026-06-10", horizon="day"),
            "LONG": _meta(first_seen="2026-01-02", horizon="long")}
    plan = ap.plan_max_hold_closes([_pos("DAYT"), _pos("LONG")], meta, "2026-06-11", set(),
                                   default_days=30)
    assert [c["symbol"] for c in plan] == ["DAYT"]     # day cap=1 -> closed; long -> exempt


def test_max_hold_disabled_and_done_key():
    meta = {"OLD": _meta(first_seen="2026-01-02")}
    assert ap.plan_max_hold_closes([_pos("OLD")], meta, "2026-06-11", set(), default_days=0) == []
    done = {"2026-06-11:OLD:maxhold_close"}
    assert ap.plan_max_hold_closes([_pos("OLD")], meta, "2026-06-11", done, default_days=30) == []


# ----------------------------------------------------------------- position_meta ledger

def test_update_meta_adopts_ratchets_hwm_and_prunes():
    legs = {"AAA": {"stop": 92.0, "target": 130.0}}
    meta, ch = pm.update_meta({}, [_pos("AAA", px=101.0)], legs, "2026-06-11")
    assert ch and meta["AAA"]["first_seen"] == "2026-06-11"
    assert meta["AAA"]["initial_stop"] == 92.0 and meta["AAA"]["hwm"] == 101.0
    meta2, ch2 = pm.update_meta(meta, [_pos("AAA", px=109.0)], legs, "2026-06-12")
    assert ch2 and meta2["AAA"]["hwm"] == 109.0
    assert meta2["AAA"]["first_seen"] == "2026-06-11"  # clock NOT reset while held
    meta3, ch3 = pm.update_meta(meta2, [], {}, "2026-06-13")  # position gone -> pruned
    assert ch3 and meta3 == {}


def test_risk_unit_real_and_proxy():
    assert pm.risk_unit({"entry": 100.0, "initial_stop": 92.0}) == 8.0
    assert pm.risk_unit({"entry": 100.0, "initial_stop": 103.0}) == pytest.approx(4.0)  # proxy
    assert pm.risk_unit({"entry": 100.0, "initial_stop": None}) == pytest.approx(4.0)
    assert pm.risk_unit({"entry": 0}) is None


# ----------------------------------------------------------------- never-loosen reprice guard

def test_adjust_cannot_loosen_stop():
    verdicts = [{"date": "2026-06-11", "symbol": "AAA", "verdict": "adjust",
                 "target": 35.0, "stop": 20.0}]                       # tries to widen risk
    positions = [{"symbol": "AAA", "qty": 10}]
    live = {"AAA": {"stop": 25.0, "target": 30.0}}
    plan = ap.plan_reprices(verdicts, positions, set(), live_stops=live)
    assert len(plan) == 1
    assert plan[0]["stop"] == 25.0 and plan[0]["clamped"] is True     # clamped to current
    assert plan[0]["target"] == 35.0                                  # target still moves


def test_adjust_noop_after_clamp_is_skipped():
    verdicts = [{"date": "2026-06-11", "symbol": "AAA", "verdict": "adjust",
                 "target": 30.0, "stop": 20.0}]                       # same target, looser stop
    positions = [{"symbol": "AAA", "qty": 10}]
    live = {"AAA": {"stop": 25.0, "target": 30.0}}
    assert ap.plan_reprices(verdicts, positions, set(), live_stops=live) == []


def test_adjust_tighten_passes_unclamped():
    verdicts = [{"date": "2026-06-11", "symbol": "AAA", "verdict": "adjust",
                 "target": 35.0, "stop": 27.0}]                       # genuine tighten
    positions = [{"symbol": "AAA", "qty": 10}]
    live = {"AAA": {"stop": 25.0, "target": 30.0}}
    plan = ap.plan_reprices(verdicts, positions, set(), live_stops=live)
    assert plan[0]["stop"] == 27.0 and plan[0]["clamped"] is False


# ----------------------------------------------------------------- sync() end-to-end

class _LifecycleBroker:
    """A held winner with a live OCO: sync's lifecycle should ratchet its stop."""
    def __init__(self):
        self.reprices, self.closes, self.buys = [], [], []

    def filled_orders(self, limit=200):
        return []

    def buy(self, *a, **k):
        return {"qty": 1, "entry": 100.0}

    def close(self, symbol):
        self.closes.append(symbol)

    def protect(self, *a, **k):
        pass

    def reprice(self, symbol, qty, target, stop):
        self.reprices.append((symbol, qty, target, stop))

    def account(self):
        return {"equity": 1_000_000.0, "cash": 1.0, "last_equity": 1_000_000.0,
                "open_positions": [{"symbol": "WIN", "qty": 50, "avg_entry_price": 100.0,
                                    "current_price": 117.0, "unrealized_pl": 850.0,
                                    "unrealized_plpc": 0.17}]}

    def open_orders(self):
        return [{"symbol": "WIN", "side": "sell", "limit_price": 130.0, "stop_price": None},
                {"symbol": "WIN", "side": "sell", "limit_price": None, "stop_price": 92.0}]


def _wire(tmp_path, monkeypatch):
    (tmp_path / "v.json").write_text("[]")
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    monkeypatch.setattr(ap, "_latest_scanner_levels", lambda: {})
    monkeypatch.setattr(pm, "META_FILE", tmp_path / "meta.json")
    monkeypatch.setenv("TONY_MARKET_SESSION", "open")
    monkeypatch.setenv("TONY_BOOK_CACHE", str(tmp_path / "book.json"))


def test_sync_ratchets_a_winner_end_to_end(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    # pre-seed meta as if the position was adopted at entry with its original stop
    pm.save_meta({"WIN": _meta()})
    b = _LifecycleBroker()
    res = ap.sync(broker=b)
    assert res["ratcheted"] == 1
    sym, qty, target, stop = b.reprices[-1]
    assert (sym, qty, target) == ("WIN", 50, 130.0) and stop == 107.0   # floor raised, target kept
    done = json.loads((tmp_path / "exec.json").read_text())
    assert any(k.startswith("ratchet:") and "WIN" in k for k in done)   # persisted -> no re-fire
    res2 = ap.sync(broker=b)
    assert res2["ratcheted"] == 0                                        # idempotent next cycle


def test_sync_max_hold_closes_old_swing(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    pm.save_meta({"WIN": _meta(first_seen="2026-01-02")})               # ancient swing position
    monkeypatch.setattr(ap, "MAX_HOLD_DAYS", 30)
    b = _LifecycleBroker()
    res = ap.sync(broker=b)
    assert res["max_hold_closed"] == 1 and b.closes == ["WIN"]


def test_sync_ratchet_gate_off(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    pm.save_meta({"WIN": _meta()})
    monkeypatch.setattr(ap, "STOP_RATCHET", False)
    monkeypatch.setattr(ap, "MAX_HOLD_DAYS", 0)
    b = _LifecycleBroker()
    res = ap.sync(broker=b)
    assert res["ratcheted"] == 0 and res["max_hold_closed"] == 0 and b.reprices == []


def test_ratchet_caps_per_cycle_biggest_gain_first():
    # 5 eligible winners; cap=2 -> only the two with the largest stop-raise fire this cycle
    legs, meta, positions = {}, {}, []
    for i, (cur, hwm) in enumerate([(92, 110), (92, 117), (92, 113), (92, 121), (92, 108)]):
        sym = f"S{i}"
        positions.append(_pos(sym, px=hwm))
        legs[sym] = {"stop": float(cur), "target": 200.0}
        meta[sym] = _meta(hwm=float(hwm))
    plan = ap.plan_stop_ratchets(positions, legs, meta, "2026-06-11", set(),
                                 be_r=0.75, trail_r=1.25, max_per_cycle=2)
    assert len(plan) == 2
    syms = {p["symbol"] for p in plan}
    assert syms == {"S3", "S1"}        # hwm 121 and 117 -> highest floors -> biggest protection gain
