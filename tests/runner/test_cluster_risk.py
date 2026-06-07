"""Tests for runner.ledger.cluster_risk — T1.9 portfolio cluster-risk cap.

Written FIRST (TDD). All tests are hermetic — data passed directly, env patched via monkeypatch.
"""
import pytest
from runner.ledger import cluster_risk as cr


# ---------------------------------------------------------------------------
# cluster_of
# ---------------------------------------------------------------------------

class TestClusterOf:
    def test_energy_tickers(self):
        for sym in ["SLB", "DVN", "XOM", "CVX", "OXY", "HAL", "COP", "XLE"]:
            assert cr.cluster_of(sym) == "energy", f"{sym} should be energy"

    def test_fcx_is_energy(self):
        # FCX is copper/materials but incident grouped it with energy complex
        assert cr.cluster_of("FCX") == "energy"

    def test_tech_tickers(self):
        for sym in ["AAPL", "MSFT", "NVDA", "CRM", "SNAP", "META", "GOOGL", "AMD", "XLK"]:
            assert cr.cluster_of(sym) == "tech", f"{sym} should be tech"

    def test_financials_tickers(self):
        for sym in ["JPM", "BAC", "GS", "WFC", "XLF"]:
            assert cr.cluster_of(sym) == "financials", f"{sym} should be financials"

    def test_healthcare_tickers(self):
        for sym in ["UNH", "JNJ", "PFE", "XLV"]:
            assert cr.cluster_of(sym) == "healthcare", f"{sym} should be healthcare"

    def test_unknown_is_other(self):
        assert cr.cluster_of("ZZZZ") == "other"
        assert cr.cluster_of("NOTREAL") == "other"

    def test_case_insensitive(self):
        assert cr.cluster_of("fcx") == "energy"
        assert cr.cluster_of("aapl") == "tech"
        assert cr.cluster_of("jpm") == "financials"
        assert cr.cluster_of("FCX") == "energy"

    def test_none_returns_other(self):
        assert cr.cluster_of(None) == "other"

    def test_non_str_returns_other(self):
        assert cr.cluster_of(123) == "other"
        assert cr.cluster_of([]) == "other"


# ---------------------------------------------------------------------------
# cluster_counts
# ---------------------------------------------------------------------------

class TestClusterCounts:
    def _pos(self, symbol, qty=10.0):
        return {"symbol": symbol, "qty": qty}

    def test_basic_counts(self):
        held = [self._pos("FCX"), self._pos("SLB"), self._pos("AAPL")]
        counts = cr.cluster_counts(held)
        assert counts.get("energy") == 2
        assert counts.get("tech") == 1

    def test_zero_qty_excluded(self):
        held = [self._pos("FCX", qty=0), self._pos("SLB", qty=5.0)]
        counts = cr.cluster_counts(held)
        assert counts.get("energy") == 1

    def test_negative_qty_excluded(self):
        held = [self._pos("XOM", qty=-1.0), self._pos("SLB", qty=2.0)]
        counts = cr.cluster_counts(held)
        assert counts.get("energy") == 1

    def test_empty_held(self):
        assert cr.cluster_counts([]) == {}

    def test_other_not_aggregated_as_cluster(self):
        # "other" symbols should not pool together under a single "other" count
        # that would cause them to hit the cap — each unknown is its own effective bucket
        held = [self._pos("ZZZZ"), self._pos("YYYY"), self._pos("XXXX")]
        counts = cr.cluster_counts(held)
        # "other" as a combined key must not exist (or be <=1 per unique symbol)
        assert counts.get("other", 0) == 0

    def test_mixed_clusters(self):
        held = [
            self._pos("FCX"), self._pos("DVN"),               # energy x2
            self._pos("AAPL"), self._pos("MSFT"), self._pos("NVDA"),  # tech x3
            self._pos("JPM"),                                  # financials x1
        ]
        counts = cr.cluster_counts(held)
        assert counts["energy"] == 2
        assert counts["tech"] == 3
        assert counts["financials"] == 1


# ---------------------------------------------------------------------------
# over_cluster_cap
# ---------------------------------------------------------------------------

class TestOverClusterCap:
    def _pos(self, symbol, qty=10.0):
        return {"symbol": symbol, "qty": qty}

    def test_over_cap_when_would_exceed(self):
        # 3 energy held, cap=3 -> adding a 4th would push count to 4 > 3 -> True
        held = [self._pos("FCX"), self._pos("SLB"), self._pos("DVN")]
        assert cr.over_cluster_cap(held, "XOM", max_per_cluster=3) is True

    def test_not_over_cap_when_at_limit_minus_one(self):
        # 2 energy held, cap=3 -> adding 3rd = exactly 3, not over -> False
        held = [self._pos("FCX"), self._pos("SLB")]
        assert cr.over_cluster_cap(held, "DVN", max_per_cluster=3) is False

    def test_not_over_cap_when_empty(self):
        assert cr.over_cluster_cap([], "FCX", max_per_cluster=3) is False

    def test_other_symbol_never_over_cap(self):
        # even if many "other" unknowns are held, a new "other" is never blocked
        held = [self._pos("ZZZZ"), self._pos("YYYY"), self._pos("XXXX"), self._pos("WWWW")]
        assert cr.over_cluster_cap(held, "QQQQ", max_per_cluster=1) is False

    def test_env_default_used_when_no_kwarg(self, monkeypatch):
        monkeypatch.setenv("TONY_MAX_PER_CLUSTER", "3")
        held = [self._pos("FCX"), self._pos("SLB"), self._pos("DVN")]
        # 3 energy, new energy -> would be 4 > 3 -> True
        assert cr.over_cluster_cap(held, "XOM") is True

    def test_env_default_of_3_when_unset(self, monkeypatch):
        monkeypatch.delenv("TONY_MAX_PER_CLUSTER", raising=False)
        held = [self._pos("FCX"), self._pos("SLB")]
        # 2 energy, cap defaults to 3 -> 3rd allowed -> False
        assert cr.over_cluster_cap(held, "DVN") is False

    def test_kwarg_overrides_env(self, monkeypatch):
        monkeypatch.setenv("TONY_MAX_PER_CLUSTER", "10")
        held = [self._pos("FCX"), self._pos("SLB")]
        # env says 10, but kwarg=2 -> 3rd would be 3 > 2 -> True
        assert cr.over_cluster_cap(held, "DVN", max_per_cluster=2) is True

    def test_different_cluster_not_blocked(self):
        # 3 energy held, but new buy is tech -> tech cluster empty -> False
        held = [self._pos("FCX"), self._pos("SLB"), self._pos("DVN")]
        assert cr.over_cluster_cap(held, "AAPL", max_per_cluster=3) is False


# ---------------------------------------------------------------------------
# filter_new_buys
# ---------------------------------------------------------------------------

class TestFilterNewBuys:
    def _pos(self, symbol, qty=10.0):
        return {"symbol": symbol, "qty": qty}

    def _buy(self, symbol, **extra):
        return {"symbol": symbol, "action": "buy", **extra}

    def _close(self, symbol, **extra):
        return {"symbol": symbol, "action": "close", **extra}

    def test_incident_scenario(self):
        """held=[FCX,SLB] (2 energy), cap=3, plan=[buy DVN, buy XOM, buy AAPL, close MSFT]
        -> DVN allowed (3rd energy=3==cap, not over), XOM blocked (would be 4th>3),
           AAPL allowed (tech), close MSFT passes through."""
        held = [self._pos("FCX"), self._pos("SLB")]
        plan = [
            self._buy("DVN"),
            self._buy("XOM"),
            self._buy("AAPL"),
            self._close("MSFT"),
        ]
        allowed, blocked = cr.filter_new_buys(plan, held, max_per_cluster=3)

        allowed_syms = [x["symbol"] for x in allowed]
        blocked_syms = [x["symbol"] for x in blocked]

        assert "DVN" in allowed_syms
        assert "XOM" in blocked_syms
        assert "AAPL" in allowed_syms
        assert "MSFT" in allowed_syms   # close passes through

    def test_blocked_reason_key(self):
        held = [self._pos("FCX"), self._pos("SLB"), self._pos("DVN")]
        plan = [self._buy("XOM")]
        _, blocked = cr.filter_new_buys(plan, held, max_per_cluster=3)
        assert len(blocked) == 1
        assert "blocked_reason" in blocked[0]
        assert "energy" in blocked[0]["blocked_reason"]
        assert "3" in blocked[0]["blocked_reason"]

    def test_incremental_simulation(self):
        """Two consecutive energy buys when 2 already held and cap=3:
        first allowed (makes 3), second blocked (would make 4)."""
        held = [self._pos("FCX"), self._pos("SLB")]
        plan = [self._buy("DVN"), self._buy("XOM")]
        allowed, blocked = cr.filter_new_buys(plan, held, max_per_cluster=3)
        assert [x["symbol"] for x in allowed] == ["DVN"]
        assert [x["symbol"] for x in blocked] == ["XOM"]

    def test_close_always_passes_through(self):
        held = [self._pos("FCX"), self._pos("SLB"), self._pos("DVN")]
        plan = [self._close("XOM"), self._close("AAPL")]
        allowed, blocked = cr.filter_new_buys(plan, held, max_per_cluster=3)
        assert len(allowed) == 2
        assert len(blocked) == 0

    def test_empty_plan(self):
        held = [self._pos("FCX")]
        allowed, blocked = cr.filter_new_buys([], held, max_per_cluster=3)
        assert allowed == []
        assert blocked == []

    def test_empty_held(self):
        plan = [self._buy("FCX"), self._buy("SLB"), self._buy("DVN"), self._buy("XOM")]
        allowed, blocked = cr.filter_new_buys(plan, [], max_per_cluster=3)
        # first 3 allowed, 4th blocked
        assert len(allowed) == 3
        assert len(blocked) == 1
        assert blocked[0]["symbol"] == "XOM"

    def test_env_default_cap_of_3(self, monkeypatch):
        monkeypatch.delenv("TONY_MAX_PER_CLUSTER", raising=False)
        held = [self._pos("FCX"), self._pos("SLB")]
        plan = [self._buy("DVN"), self._buy("XOM")]
        allowed, blocked = cr.filter_new_buys(plan, held)
        # env default 3: DVN allowed (3rd), XOM blocked (4th)
        assert [x["symbol"] for x in allowed] == ["DVN"]
        assert [x["symbol"] for x in blocked] == ["XOM"]

    def test_kwarg_cap_override(self, monkeypatch):
        monkeypatch.delenv("TONY_MAX_PER_CLUSTER", raising=False)
        held = [self._pos("FCX")]
        plan = [self._buy("SLB"), self._buy("DVN")]
        # cap=2: FCX already held (1), SLB allowed (2=cap), DVN blocked (3>2)
        allowed, blocked = cr.filter_new_buys(plan, held, max_per_cluster=2)
        assert [x["symbol"] for x in allowed] == ["SLB"]
        assert [x["symbol"] for x in blocked] == ["DVN"]

    def test_other_symbols_never_blocked(self, monkeypatch):
        monkeypatch.delenv("TONY_MAX_PER_CLUSTER", raising=False)
        held = [self._pos("ZZZZ"), self._pos("YYYY"), self._pos("XXXX")]
        plan = [self._buy("QQQQ"), self._buy("PPPP")]
        # "other" uncapped -> all pass
        allowed, blocked = cr.filter_new_buys(plan, held, max_per_cluster=1)
        assert len(allowed) == 2
        assert len(blocked) == 0

    def test_blocked_item_not_mutated_original(self):
        """filter_new_buys must not mutate the original plan item dict when blocking."""
        held = [self._pos("FCX"), self._pos("SLB"), self._pos("DVN")]
        item = self._buy("XOM")
        original_keys = set(item.keys())
        _, blocked = cr.filter_new_buys([item], held, max_per_cluster=3)
        # original dict should be unchanged (we add blocked_reason to a copy)
        assert set(item.keys()) == original_keys

    def test_mixed_actions(self):
        held = [self._pos("FCX"), self._pos("SLB")]
        plan = [
            self._buy("DVN"),
            {"symbol": "AAPL", "action": "adjust"},   # unknown action -> passes through
            self._buy("XOM"),
            self._close("COP"),
        ]
        allowed, blocked = cr.filter_new_buys(plan, held, max_per_cluster=3)
        allowed_syms = [x["symbol"] for x in allowed]
        blocked_syms = [x["symbol"] for x in blocked]
        assert "DVN" in allowed_syms
        assert "AAPL" in allowed_syms   # non-buy passes
        assert "XOM" in blocked_syms
        assert "COP" in allowed_syms    # close passes
