"""B1 — conviction-weighted sizing: confidence scales risk %, gated on proven calibration, with a
pure picking-vs-sizing attribution. Default (flag off) must be byte-for-byte today's flat sizing.
"""
import json

from runner.ledger import alpaca_paper as ap
from runner.ledger import tony_scorecard as tsc


class FakeBroker:
    def __init__(self, fills=None):
        self.buys = []
        self.buy_risk_pcts = []
        self._fills = fills or []

    def filled_orders(self, limit=200):
        return self._fills

    def buy(self, symbol, notional, target, stop, risk_pct=None):
        self.buys.append(symbol)
        self.buy_risk_pcts.append(risk_pct)
        return {"qty": 10, "entry": 100.0}

    def close(self, symbol):
        pass

    def protect(self, symbol, qty, target, stop):
        pass

    def reprice(self, symbol, qty, target, stop):
        pass

    def account(self):
        return {"equity": 1_000_000.0, "cash": 1_000_000.0, "last_equity": 1_000_000.0, "open_positions": []}

    def open_orders(self):
        return []


# ----------------------------- multiplier -----------------------------

def test_conviction_multiplier_defaults():
    assert ap.conviction_multiplier("low") == 0.5
    assert ap.conviction_multiplier("medium") == 1.0
    assert ap.conviction_multiplier("high") == 1.5
    assert ap.conviction_multiplier("HIGH") == 1.5      # case-insensitive
    assert ap.conviction_multiplier(None) == 1.0        # unknown -> flat
    assert ap.conviction_multiplier("garbage") == 1.0


def test_conviction_multiplier_env_overridable(monkeypatch):
    monkeypatch.setenv("TONY_CONV_MULT_HIGH", "2.0")
    assert ap.conviction_multiplier("high") == 2.0


# ----------------------------- gate -----------------------------

def test_gate_off_by_default(monkeypatch):
    monkeypatch.delenv("TONY_CONVICTION_SIZING", raising=False)
    assert ap.conviction_enabled() is False


def test_gate_on_forces_true(monkeypatch):
    monkeypatch.setenv("TONY_CONVICTION_SIZING", "on")
    assert ap.conviction_enabled() is True


def test_gate_auto_requires_graded_and_calibration_gap(monkeypatch):
    monkeypatch.setenv("TONY_CONVICTION_SIZING", "auto")
    # too few graded -> off
    monkeypatch.setattr(tsc, "compute_record",
                        lambda: {"graded": 5, "calibration": {"high": 80, "low": 50}})
    assert ap.conviction_enabled() is False
    # enough graded but calibration gap too small -> off
    monkeypatch.setattr(tsc, "compute_record",
                        lambda: {"graded": 30, "calibration": {"high": 55, "low": 52}})
    assert ap.conviction_enabled() is False
    # enough graded AND high beats low by >= 10 -> on
    monkeypatch.setattr(tsc, "compute_record",
                        lambda: {"graded": 30, "calibration": {"high": 70, "low": 50}})
    assert ap.conviction_enabled() is True
    # missing buckets -> off
    monkeypatch.setattr(tsc, "compute_record",
                        lambda: {"graded": 30, "calibration": {"high": None, "low": 50}})
    assert ap.conviction_enabled() is False


# ----------------------------- plan carries confidence -----------------------------

def test_plan_orders_carries_confidence():
    verdicts = [{"date": "2026-06-05", "symbol": "AAA", "verdict": "override",
                 "target": 30, "stop": 25, "confidence": "high"}]
    plan = ap.plan_orders(verdicts, set())
    assert plan[0]["confidence"] == "high"
    # close actions stay untouched (no confidence key forced on them)
    cplan = ap.plan_orders([{"date": "2026-06-05", "symbol": "B", "verdict": "close"}], set())
    assert "confidence" not in cplan[0]


# ----------------------------- naked-entry guard -----------------------------

def test_plan_orders_skips_open_with_no_levels():
    # No target/stop on the verdict and no scanner level to inherit -> not opened
    # (would otherwise become a naked, off-size flat-notional buy).
    verdicts = [{"date": "2026-06-05", "symbol": "NAKED", "verdict": "override"}]
    assert ap.plan_orders(verdicts, set(), scanner_levels={}) == []


def test_plan_orders_inherits_scanner_levels():
    # No levels of its own, but the scanner provides them -> still opened (bracket).
    verdicts = [{"date": "2026-06-05", "symbol": "INH", "verdict": "override"}]
    plan = ap.plan_orders(verdicts, set(), scanner_levels={"INH": {"target": 30, "stop": 25}})
    assert len(plan) == 1
    assert plan[0]["action"] == "buy"
    assert plan[0]["target"] == 30 and plan[0]["stop"] == 25


def test_plan_orders_keeps_open_with_own_levels():
    verdicts = [{"date": "2026-06-05", "symbol": "OWN", "verdict": "override", "target": 30, "stop": 25}]
    plan = ap.plan_orders(verdicts, set(), scanner_levels={})
    assert len(plan) == 1 and plan[0]["action"] == "buy"


# ----------------------------- same-session re-entry block -----------------------------

def test_symbols_exited_today_filters_sells_by_date():
    fills = [
        {"symbol": "KDP", "side": "sell", "date": "2026-06-08"},
        {"symbol": "OLD", "side": "sell", "date": "2026-06-07"},   # prior day -> not blocked
        {"symbol": "BUY", "side": "buy", "date": "2026-06-08"},    # a buy, not an exit
    ]
    assert ap.symbols_exited_today(fills, "2026-06-08") == {"KDP"}


def test_plan_orders_blocks_reentry_after_exit_today():
    # KDP exited today -> no re-open today, even with valid levels.
    verdicts = [{"date": "2026-06-08", "symbol": "KDP", "verdict": "override", "target": 30, "stop": 25}]
    assert ap.plan_orders(verdicts, set(), scanner_levels={}, exited_today={"KDP"}) == []
    # a different name is unaffected
    plan = ap.plan_orders(verdicts, set(), scanner_levels={}, exited_today={"OTHER"})
    assert len(plan) == 1 and plan[0]["action"] == "buy"


def test_sync_skips_symbol_exited_today(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch, [{"date": "2026-06-08", "symbol": "KDP", "verdict": "override",
                                   "target": 30, "stop": 25, "confidence": "high"}])
    from runner.ledger.market_clock import trading_day
    today = trading_day()  # the clock sync uses; a real RTH fill always carries the ET day
    b = FakeBroker(fills=[{"symbol": "KDP", "side": "sell", "date": today}])
    ap.sync(broker=b)
    assert "KDP" not in b.buys


# ----------------------------- nested OCO leg visibility (protection reconcile) -----------------------------

from types import SimpleNamespace


def _oco(symbol, tp_id, tp, stop_id, stop):
    """An OCO sell: top-level take-profit LIMIT with the stop-loss as a HELD child leg (how Alpaca
    returns it with nested=True)."""
    leg = SimpleNamespace(id=stop_id, symbol=symbol, side="sell", qty=39, notional=None,
                          order_class="oco", order_type="stop", limit_price=None, stop_price=stop,
                          status="held", legs=None)
    return SimpleNamespace(id=tp_id, symbol=symbol, side="sell", qty=39, notional=None,
                           order_class="oco", order_type="limit", limit_price=tp, stop_price=None,
                           status="new", legs=[leg])


def test_flatten_orders_surfaces_held_stop_leg():
    flat = ap._flatten_orders([_oco("DKNG", "p1", 33.5, "l1", 22.85)])
    assert len(flat) == 2
    stop = [o for o in flat if o["type"] == "stop"][0]
    assert stop["symbol"] == "DKNG" and stop["stop_price"] == 22.85 and stop["parent_id"] == "p1"
    # the take-profit parent is top-level (no parent_id) -> cancel logic targets it, not the leg
    tp = [o for o in flat if o["type"] == "limit"][0]
    assert tp["parent_id"] is None


def test_flatten_orders_drops_terminal():
    o = SimpleNamespace(id="x", symbol="A", side="sell", qty=1, notional=None, order_class="simple",
                        order_type="limit", limit_price=10, stop_price=None, status="filled", legs=None)
    assert ap._flatten_orders([o]) == []


def test_flatten_keeps_live_legs_under_filled_bracket_entry():
    # buy() uses OrderClass.BRACKET. Once the entry fills it's terminal, but its protective legs
    # are live — they must NOT be dropped, or the position looks naked and gets churned.
    tp = SimpleNamespace(id="tp", symbol="X", side="sell", qty=10, notional=None, order_class="bracket",
                         order_type="limit", limit_price=50, stop_price=None, status="held", legs=None)
    sl = SimpleNamespace(id="sl", symbol="X", side="sell", qty=10, notional=None, order_class="bracket",
                         order_type="stop", limit_price=None, stop_price=40, status="held", legs=None)
    entry = SimpleNamespace(id="e", symbol="X", side="buy", qty=10, notional=None, order_class="bracket",
                            order_type="market", limit_price=None, stop_price=None, status="filled",
                            legs=[tp, sl])
    flat = ap._flatten_orders([entry])
    pairs = {(o["symbol"], o["type"]) for o in flat}
    assert ("X", "stop") in pairs and ("X", "limit") in pairs   # legs survive
    assert all(o["status"] != "filled" for o in flat)           # the terminal entry is dropped
    # and the position is now correctly seen as protected
    assert ap.positions_needing_protection([{"symbol": "X", "qty": 10, "avg_entry_price": 45.0}], flat, {}) == []


def test_position_protected_by_nested_stop_not_flagged():
    # The bug: a position guarded by an OCO whose stop sits in a leg looked "naked" and got its
    # OCO cancelled every cycle. With legs surfaced, it's correctly seen as protected.
    positions = [{"symbol": "DKNG", "qty": 39, "avg_entry_price": 28.0}]
    orders = ap._flatten_orders([_oco("DKNG", "p1", 33.5, "l1", 22.85)])
    assert ap.positions_needing_protection(positions, orders, {}) == []


def test_entry_qty_fixed_notional():
    # $10k / $200 = 50 shares; flat regardless of any stop. Conviction mult scales it; bad price -> 1.
    assert ap.entry_qty(200.0) == 50
    assert ap.entry_qty(50.0) == 200
    assert ap.entry_qty(200.0, mult=1.5) == 75
    assert ap.entry_qty(200.0, mult=0.5) == 25
    assert ap.entry_qty(0) == 1


def test_truly_naked_position_still_flagged():
    positions = [{"symbol": "KDP", "qty": 50, "avg_entry_price": 31.0}]
    lone_tp = [{"symbol": "KDP", "side": "sell", "type": "limit", "stop_price": None, "parent_id": None}]
    needs = ap.positions_needing_protection(positions, lone_tp, {}, fallback_pct=(0.12, 0.20))
    assert [n["symbol"] for n in needs] == ["KDP"]


# ----------------------------- sync wiring -----------------------------

def _wire(tmp_path, monkeypatch, verdicts):
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    monkeypatch.setattr(ap, "_latest_scanner_levels", lambda: {})
    import runner.ledger.position_meta as _pm
    monkeypatch.setattr(_pm, "META_FILE", tmp_path / "position-meta.json")  # lifecycle ledger isolation
    monkeypatch.setenv("TONY_MARKET_SESSION", "open")  # exercise buy mechanics regardless of wall-clock (weekend-safe)


def test_sync_flat_when_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("TONY_CONVICTION_SIZING", raising=False)  # default off
    _wire(tmp_path, monkeypatch, [{"date": "2026-06-05", "symbol": "AAA", "verdict": "override",
                                   "target": 30, "stop": 25, "confidence": "high"}])
    b = FakeBroker()
    ap.sync(broker=b)
    assert b.buy_risk_pcts == [ap.RISK_PCT]  # high conviction ignored -> flat 1%


def test_sync_scales_risk_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_CONVICTION_SIZING", "on")
    _wire(tmp_path, monkeypatch, [
        {"date": "2026-06-05", "symbol": "HI", "verdict": "override", "target": 30, "stop": 25, "confidence": "high"},
        {"date": "2026-06-05", "symbol": "LO", "verdict": "override", "target": 30, "stop": 25, "confidence": "low"},
    ])
    b = FakeBroker()
    ap.sync(broker=b)
    by_sym = dict(zip(b.buys, b.buy_risk_pcts))
    assert by_sym["HI"] == ap.RISK_PCT * 1.5
    assert by_sym["LO"] == ap.RISK_PCT * 0.5


# ----------------------------- attribution -----------------------------

def test_sizing_attribution_decomposes(tmp_path, monkeypatch):
    # high-confidence winner + low-confidence loser: conviction weighting should beat equal weight.
    verdicts = [
        {"date": "2026-06-01", "symbol": "WIN", "verdict": "override", "confidence": "high", "stop": 90},
        {"date": "2026-06-01", "symbol": "LOSE", "verdict": "override", "confidence": "low", "stop": 90},
    ]
    outcomes = [
        {"symbol": "WIN", "pick_date": "2026-06-01", "return_pct": 10.0},
        {"symbol": "LOSE", "pick_date": "2026-06-01", "return_pct": -10.0},
    ]
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    (tmp_path / "o.json").write_text(json.dumps(outcomes))
    monkeypatch.setattr(tsc, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(tsc, "OUTCOMES_FILE", tmp_path / "o.json")
    sa = tsc.sizing_attribution()
    assert sa["status"] == "scored" and sa["graded"] == 2
    assert sa["flat_return_pct"] == 0.0                       # (10 + -10)/2
    assert sa["picking_alpha_pct"] == 0.0                     # selection quality at flat sizing
    # conviction: (1.5*10 + 0.5*-10) / (1.5+0.5) = 10/2 = 5.0
    assert sa["conviction_return_pct"] == 5.0
    assert sa["sizing_alpha_pct"] == 5.0                      # sizing added +5% here


def test_sizing_attribution_awaiting_without_outcomes(tmp_path, monkeypatch):
    (tmp_path / "v.json").write_text(json.dumps([]))
    (tmp_path / "o.json").write_text(json.dumps([]))
    monkeypatch.setattr(tsc, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(tsc, "OUTCOMES_FILE", tmp_path / "o.json")
    assert tsc.sizing_attribution()["status"] == "awaiting_outcomes"
