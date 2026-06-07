"""B1 — conviction-weighted sizing: confidence scales risk %, gated on proven calibration, with a
pure picking-vs-sizing attribution. Default (flag off) must be byte-for-byte today's flat sizing.
"""
import json

from runner.ledger import alpaca_paper as ap
from runner.ledger import tony_scorecard as tsc


class FakeBroker:
    def __init__(self):
        self.buys = []
        self.buy_risk_pcts = []

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
        return {"equity": 1_000_000.0, "cash": 1.0, "last_equity": 1_000_000.0, "open_positions": []}

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


# ----------------------------- sync wiring -----------------------------

def _wire(tmp_path, monkeypatch, verdicts):
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    monkeypatch.setattr(ap, "_latest_scanner_levels", lambda: {})
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
