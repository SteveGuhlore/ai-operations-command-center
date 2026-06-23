"""Tests for runner.ledger.drawdown_breaker — written FIRST (TDD).

Friday 2026-06-06 incident: 4 consecutive stop-outs (FCX, SLB, SNAP, DVN, ~-$945).
The breaker must catch that cluster before new entries are taken.
"""

import json
import math
import os

import pytest

from runner.ledger import drawdown_breaker as db


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _row(symbol, pl, date="2026-06-06", reason="stop", exit_order_id=None):
    return {
        "symbol": symbol,
        "qty": 10.0,
        "entry": 100.0,
        "exit": 100.0 + pl / 10.0,
        "realized_pl": float(pl),
        "pct": pl,
        "reason": reason,
        "date": date,
        "exit_order_id": exit_order_id or f"ord-{symbol}",
    }


FRIDAY_ROWS = [
    _row("FCX", -236.0),
    _row("SLB", -235.0),
    _row("SNAP", -237.0),
    _row("DVN", -237.0),
]


# ---------------------------------------------------------------------------
# consecutive_losses
# ---------------------------------------------------------------------------


class TestConsecutiveLosses:
    def test_friday_four_consecutive_stop_outs(self):
        assert db.consecutive_losses(FRIDAY_ROWS) == 4

    def test_win_in_middle_resets(self):
        rows = [
            _row("A", -100.0, date="2026-06-01"),
            _row("B", +50.0, date="2026-06-02"),  # win resets the run
            _row("C", -80.0, date="2026-06-03"),
            _row("D", -90.0, date="2026-06-04"),
        ]
        assert db.consecutive_losses(rows) == 2

    def test_win_at_the_end_returns_zero(self):
        rows = [
            _row("A", -100.0, date="2026-06-01"),
            _row("B", -80.0, date="2026-06-02"),
            _row("C", +40.0, date="2026-06-03"),  # last trade is a win
        ]
        assert db.consecutive_losses(rows) == 0

    def test_empty_rows_returns_zero(self):
        assert db.consecutive_losses([]) == 0

    def test_single_loss(self):
        assert db.consecutive_losses([_row("X", -50.0)]) == 1

    def test_single_win(self):
        assert db.consecutive_losses([_row("X", +50.0)]) == 0

    def test_breakeven_resets(self):
        rows = [
            _row("A", -100.0, date="2026-06-01"),
            _row("B", 0.0, date="2026-06-02"),  # break-even resets (realized_pl >= 0)
            _row("C", -60.0, date="2026-06-03"),
        ]
        assert db.consecutive_losses(rows) == 1

    def test_sort_is_applied_by_date_then_tiebreak(self):
        # Give the same date but different symbols: stable tiebreak by symbol.
        # Verify sort happens inside the function (not pre-sorted by caller).
        rows = [
            _row("Z", -10.0, date="2026-06-06"),
            _row("A", +100.0, date="2026-06-05"),  # earlier date, win
            _row("M", -10.0, date="2026-06-06"),
        ]
        # After sort: A(win, 06-05), M(loss, 06-06), Z(loss, 06-06) -> 2 trailing losses
        assert db.consecutive_losses(rows) == 2

    def test_all_losses(self):
        rows = [
            _row(s, -50.0, date="2026-06-0" + str(i + 1)) for i, s in enumerate("ABCDE")
        ]
        assert db.consecutive_losses(rows) == 5

    def test_all_wins(self):
        rows = [
            _row(s, +50.0, date="2026-06-0" + str(i + 1)) for i, s in enumerate("ABCDE")
        ]
        assert db.consecutive_losses(rows) == 0


# ---------------------------------------------------------------------------
# max_drawdown_pct
# ---------------------------------------------------------------------------


class TestMaxDrawdownPct:
    def test_standard_series(self):
        # [100, 110, 90, 95]: peak 110, trough 90 -> (110-90)/110 * 100 = 18.18...%
        result = db.max_drawdown_pct([100.0, 110.0, 90.0, 95.0])
        assert math.isclose(result, (110 - 90) / 110 * 100, rel_tol=1e-6)

    def test_monotonic_up_returns_zero(self):
        assert db.max_drawdown_pct([100.0, 105.0, 110.0, 120.0]) == 0.0

    def test_empty_returns_zero(self):
        assert db.max_drawdown_pct([]) == 0.0

    def test_single_point_returns_zero(self):
        assert db.max_drawdown_pct([100.0]) == 0.0

    def test_two_points_drop(self):
        # 100 -> 80: 20% drawdown
        result = db.max_drawdown_pct([100.0, 80.0])
        assert math.isclose(result, 20.0, rel_tol=1e-6)

    def test_two_points_up(self):
        assert db.max_drawdown_pct([80.0, 100.0]) == 0.0

    def test_multiple_drawdowns_picks_largest(self):
        # small dip then large dip
        result = db.max_drawdown_pct([100.0, 95.0, 98.0, 110.0, 80.0])
        # largest is from 110 to 80 = 27.27%
        assert math.isclose(result, (110 - 80) / 110 * 100, rel_tol=1e-6)

    def test_returns_positive_number(self):
        result = db.max_drawdown_pct([100.0, 90.0])
        assert result > 0.0

    def test_flat_series_returns_zero(self):
        assert db.max_drawdown_pct([100.0, 100.0, 100.0]) == 0.0


# ---------------------------------------------------------------------------
# breaker_state
# ---------------------------------------------------------------------------


class TestBreakerState:
    def test_four_consecutive_losses_halts(self, monkeypatch):
        # Friday incident: 4 stop-outs must halt (default max_consec=3)
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        state = db.breaker_state(FRIDAY_ROWS)
        assert state["halted"] is True
        assert state["throttle_mult"] == 0.0
        assert state["consecutive_losses"] == 4
        assert any("consecutive" in r.lower() for r in state["reasons"])

    def test_three_consecutive_losses_halts_at_default(self, monkeypatch):
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        rows = [_row(s, -50.0) for s in ["A", "B", "C"]]
        state = db.breaker_state(rows)
        assert state["halted"] is True
        assert state["throttle_mult"] == 0.0

    def test_two_losses_soft_zone_throttle(self, monkeypatch):
        # 2 losses, default max_consec=3 -> ceil(3/2)=2 -> soft zone
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        rows = [_row("A", -50.0), _row("B", -60.0)]
        state = db.breaker_state(rows)
        assert state["halted"] is False
        assert state["throttle_mult"] == 0.5
        assert len(state["reasons"]) > 0

    def test_zero_losses_flat_equity_clear(self, monkeypatch):
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        rows = [_row("A", +100.0), _row("B", +50.0)]
        state = db.breaker_state(rows, [100.0, 101.0, 102.0])
        assert state["halted"] is False
        assert state["throttle_mult"] == 1.0
        assert state["reasons"] == []

    def test_drawdown_halts_with_no_losses(self, monkeypatch):
        # 10% drawdown, default max_dd_pct=8.0 -> halted
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        equity = [100_000.0, 110_000.0, 99_000.0]  # peak 110k, trough 99k -> 10%
        state = db.breaker_state([], equity)
        assert state["halted"] is True
        assert state["throttle_mult"] == 0.0
        assert any("drawdown" in r.lower() for r in state["reasons"])
        assert state["drawdown_pct"] > 8.0

    def test_drawdown_soft_zone(self, monkeypatch):
        # 5% drawdown, default max_dd_pct=8.0 -> soft zone (5 >= 4.0)
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        equity = [100_000.0, 110_000.0, 104_500.0]  # peak 110k, trough 104.5k -> 5%
        state = db.breaker_state([], equity)
        assert state["halted"] is False
        assert state["throttle_mult"] == 0.5
        assert len(state["reasons"]) > 0

    def test_explicit_kwargs_override_env(self, monkeypatch):
        # env says max_consec=10 (would not trip), but explicit kwarg=2 -> halts on 2 losses
        monkeypatch.setenv("TONY_BREAKER_MAX_CONSEC_LOSSES", "10")
        monkeypatch.setenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", "50.0")
        rows = [_row("A", -50.0), _row("B", -60.0)]
        state = db.breaker_state(rows, max_consec=2)
        assert state["halted"] is True

    def test_explicit_throttle_mult_kwarg(self, monkeypatch):
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        rows = [_row("A", -50.0), _row("B", -60.0)]  # 2 losses -> soft zone
        state = db.breaker_state(rows, throttle_mult=0.25)
        assert state["halted"] is False
        assert state["throttle_mult"] == 0.25

    def test_env_max_consec_read_at_call_time(self, monkeypatch):
        monkeypatch.setenv("TONY_BREAKER_MAX_CONSEC_LOSSES", "2")
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        rows = [_row("A", -50.0), _row("B", -60.0)]
        state = db.breaker_state(rows)
        assert state["halted"] is True  # env says max_consec=2, 2 losses >= 2 -> halt

    def test_both_triggers_both_reasons(self, monkeypatch):
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        equity = [100_000.0, 110_000.0, 99_000.0]  # 10% drawdown
        state = db.breaker_state(FRIDAY_ROWS, equity)
        assert state["halted"] is True
        reasons_lower = [r.lower() for r in state["reasons"]]
        assert any("consecutive" in r for r in reasons_lower)
        assert any("drawdown" in r for r in reasons_lower)

    def test_state_keys_always_present(self, monkeypatch):
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        state = db.breaker_state([])
        for key in (
            "halted",
            "throttle_mult",
            "consecutive_losses",
            "drawdown_pct",
            "reasons",
        ):
            assert key in state

    def test_none_equity_series_ignored(self, monkeypatch):
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        state = db.breaker_state([], equity_series=None)
        assert state["drawdown_pct"] == 0.0


# ---------------------------------------------------------------------------
# load_realized_rows
# ---------------------------------------------------------------------------


class TestLoadRealizedRows:
    def test_reads_valid_file(self, tmp_path, monkeypatch):
        f = tmp_path / "realized.json"
        rows = [
            {
                "symbol": "X",
                "realized_pl": -50.0,
                "date": "2026-06-06",
                "reason": "stop",
            }
        ]
        f.write_text(json.dumps(rows), encoding="utf-8")
        monkeypatch.setenv("TONY_REALIZED_FILE", str(f))
        result = db.load_realized_rows()
        assert len(result) == 1 and result[0]["symbol"] == "X"

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TONY_REALIZED_FILE", str(tmp_path / "nonexistent.json"))
        assert db.load_realized_rows() == []

    def test_corrupt_json_returns_empty(self, tmp_path, monkeypatch):
        f = tmp_path / "realized.json"
        f.write_text("not-json", encoding="utf-8")
        monkeypatch.setenv("TONY_REALIZED_FILE", str(f))
        assert db.load_realized_rows() == []

    def test_non_list_json_returns_empty(self, tmp_path, monkeypatch):
        f = tmp_path / "realized.json"
        f.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        monkeypatch.setenv("TONY_REALIZED_FILE", str(f))
        assert db.load_realized_rows() == []


# ---------------------------------------------------------------------------
# _load_equity_series (internal, tested via current_breaker or directly)
# ---------------------------------------------------------------------------


class TestLoadEquitySeries:
    def test_reads_tony_field(self, tmp_path, monkeypatch):
        pts = [
            {"ts": "t1", "tony": 1_000_000.0, "bot": 100_000.0},
            {"ts": "t2", "tony": 990_000.0, "bot": 101_000.0},
        ]
        f = tmp_path / "equity.json"
        f.write_text(json.dumps(pts), encoding="utf-8")
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(f))
        series = db._load_equity_series()
        assert series == [1_000_000.0, 990_000.0]

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(tmp_path / "nope.json"))
        assert db._load_equity_series() == []

    def test_corrupt_returns_empty(self, tmp_path, monkeypatch):
        f = tmp_path / "equity.json"
        f.write_text("garbage", encoding="utf-8")
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(f))
        assert db._load_equity_series() == []

    def test_empty_list_returns_empty(self, tmp_path, monkeypatch):
        f = tmp_path / "equity.json"
        f.write_text("[]", encoding="utf-8")
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(f))
        assert db._load_equity_series() == []

    def test_skips_none_tony_values(self, tmp_path, monkeypatch):
        pts = [
            {"ts": "t1", "tony": 100.0, "bot": 50.0},
            {"ts": "t2", "tony": None, "bot": 50.0},
            {"ts": "t3", "tony": 95.0, "bot": 50.0},
        ]
        f = tmp_path / "equity.json"
        f.write_text(json.dumps(pts), encoding="utf-8")
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(f))
        series = db._load_equity_series()
        assert series == [100.0, 95.0]

    def test_unknown_shape_returns_empty(self, tmp_path, monkeypatch):
        # e.g. a flat list of numbers — no tony key -> fail-soft
        f = tmp_path / "equity.json"
        f.write_text(json.dumps([1.0, 2.0, 3.0]), encoding="utf-8")
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(f))
        assert db._load_equity_series() == []


# ---------------------------------------------------------------------------
# current_breaker (smoke test — just verify it doesn't raise)
# ---------------------------------------------------------------------------


class TestCurrentBreaker:
    def test_does_not_raise_with_empty_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TONY_REALIZED_FILE", str(tmp_path / "r.json"))
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(tmp_path / "e.json"))
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        state = db.current_breaker()
        assert isinstance(state, dict)
        assert "halted" in state

    def test_does_not_raise_with_real_data(self, tmp_path, monkeypatch):
        rf = tmp_path / "realized.json"
        rf.write_text(json.dumps(FRIDAY_ROWS), encoding="utf-8")
        ef = tmp_path / "equity.json"
        pts = [{"ts": "t1", "tony": 1_000_000.0, "bot": 100_000.0}]
        ef.write_text(json.dumps(pts), encoding="utf-8")
        monkeypatch.setenv("TONY_REALIZED_FILE", str(rf))
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(ef))
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)
        state = db.current_breaker()
        assert state["halted"] is True  # 4 Friday losses must still trip the breaker


# ---------------------------------------------------------------------------
# Fail-closed on unknown risk state (corrupt vs missing files)
# ---------------------------------------------------------------------------
class TestFailClosedOnUnknownState:
    def _clear_thresholds(self, monkeypatch):
        monkeypatch.delenv("TONY_BREAKER_MAX_CONSEC_LOSSES", raising=False)
        monkeypatch.delenv("TONY_BREAKER_MAX_DRAWDOWN_PCT", raising=False)
        monkeypatch.delenv("TONY_BREAKER_THROTTLE_MULT", raising=False)

    def test_missing_files_are_a_clean_cold_start(self, tmp_path, monkeypatch):
        # A *missing* ledger/equity file = no trades yet => must NOT halt.
        self._clear_thresholds(monkeypatch)
        monkeypatch.setenv("TONY_REALIZED_FILE", str(tmp_path / "nope-realized.json"))
        monkeypatch.setenv(
            "TONY_EQUITY_HISTORY_FILE", str(tmp_path / "nope-equity.json")
        )
        state = db.current_breaker()
        assert state["halted"] is False

    def test_corrupt_realized_ledger_fails_closed(self, tmp_path, monkeypatch):
        # Regression: an existing-but-corrupt ledger previously read as [] (=> all clear).
        self._clear_thresholds(monkeypatch)
        rf = tmp_path / "realized.json"
        rf.write_text("{ not json", encoding="utf-8")
        monkeypatch.setenv("TONY_REALIZED_FILE", str(rf))
        monkeypatch.setenv(
            "TONY_EQUITY_HISTORY_FILE", str(tmp_path / "missing-eq.json")
        )
        state = db.current_breaker()
        assert state["halted"] is True
        assert state["throttle_mult"] == 0.0
        assert any("unknown" in r for r in state["reasons"])

    def test_corrupt_equity_history_fails_closed(self, tmp_path, monkeypatch):
        self._clear_thresholds(monkeypatch)
        ef = tmp_path / "equity.json"
        ef.write_text("totally not json", encoding="utf-8")
        monkeypatch.setenv("TONY_REALIZED_FILE", str(tmp_path / "missing-r.json"))
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(ef))
        assert db.current_breaker()["halted"] is True

    def test_malformed_equity_shape_fails_closed(self, tmp_path, monkeypatch):
        self._clear_thresholds(monkeypatch)
        ef = tmp_path / "equity.json"
        ef.write_text(json.dumps({"unexpected": "obj"}), encoding="utf-8")
        monkeypatch.setenv("TONY_REALIZED_FILE", str(tmp_path / "missing-r.json"))
        monkeypatch.setenv("TONY_EQUITY_HISTORY_FILE", str(ef))
        assert db.current_breaker()["halted"] is True

    def test_breaker_state_default_state_known_unchanged(self):
        # Direct breaker_state callers (e.g. eval harness) keep prior behavior.
        assert db.breaker_state([], []) == db.breaker_state([], [], state_known=True)


def test_equity_path_honors_writer_env_name(monkeypatch, tmp_path):
    # M13: the breaker must resolve the SAME equity file the writer uses. Setting only
    # the writer's var (TONY_EQUITY_HISTORY) must be honored by this reader too.
    monkeypatch.delenv("TONY_EQUITY_HISTORY_FILE", raising=False)
    p = tmp_path / "eq.json"
    monkeypatch.setenv("TONY_EQUITY_HISTORY", str(p))
    assert db._equity_path() == p
