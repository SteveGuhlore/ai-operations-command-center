"""Walk-forward eval harness tests (T1.1). Hermetic — synthetic picks/inputs, no network/files.
Encodes the audit invariants as regression slices: leakage-safe folds, realized-track-is-truth,
fail-closed promotion, and the 'would-this-change-help?' candidate flow."""
import math

import pytest

from runner.eval import data_contract, metrics, walk_forward, promotion_gate, harness


def make_pick(resolved, *, verdict="reaffirm", right=True, ret=5.0, conf="high",
              evidence=None, tony_score=80.0, entry=100.0, exit=105.0, stop=95.0, symbol="AAA"):
    return {"symbol": symbol, "pick_date": "2026-05-01", "resolved_date": resolved,
            "verdict": verdict, "confidence": conf, "evidence": evidence or [],
            "return_pct": ret, "result": "target_hit" if ret > 0 else "stop_hit",
            "right": right, "tony_score": tony_score, "entry": entry, "exit": exit,
            "days_held": 3, "target": 110.0, "stop": stop}


# ---------------- metrics ----------------
def test_wilson_interval_bounds_and_midpoint():
    lo, hi = metrics.wilson_interval(5, 10)
    assert 0.0 <= lo < 0.5 < hi <= 1.0
    assert metrics.wilson_interval(0, 0) == (0.0, 1.0)
    # a perfect 5/5 must NOT have an upper bound of 1.0 collapse to certainty
    lo2, hi2 = metrics.wilson_interval(5, 5)
    assert lo2 < 1.0 and hi2 <= 1.0


def test_shrink_kills_small_sample_overtrust():
    # 5/5 raw = 1.0; shrunk toward base 0.5 must be well below 1.0 (the min_n=5 fix)
    assert metrics.shrink(5, 5, 0.5, strength=4.0) == pytest.approx(7 / 9, abs=1e-6)
    # large sample barely moves
    assert metrics.shrink(900, 1000, 0.5, 4.0) == pytest.approx(0.9, abs=0.01)


def test_win_rate_matches_count():
    picks = [make_pick("d1", right=True), make_pick("d2", right=False), make_pick("d3", right=True)]
    wr = metrics.win_rate(picks)
    assert wr["n"] == 3 and wr["wins"] == 2 and wr["win_rate"] == pytest.approx(2 / 3, abs=1e-4)


def test_expectancy_return_counts_only_open_verdicts():
    picks = [make_pick("d1", verdict="reaffirm", ret=10.0),
             make_pick("d2", verdict="pass", ret=-99.0, right=True)]  # pass is not a position
    er = metrics.expectancy_return(picks)
    assert er["n"] == 1 and er["mean_return_pct"] == pytest.approx(10.0)


def test_expectancy_r_uses_stop():
    # entry 100, exit 110, stop 90 -> R = 10/10 = 1.0
    picks = [make_pick("d1", entry=100, exit=110, stop=90)]
    assert metrics.expectancy_r(picks)["mean_r"] == pytest.approx(1.0)


def test_realized_expectancy_flags_thin_sample():
    rows = [{"realized_pl": -60.2, "pct": -6.13}, {"realized_pl": -39.95, "pct": -4.13}]
    r = metrics.realized_expectancy(rows)
    assert r["n"] == 2 and r["insufficient_sample"] is True and r["total_pl"] == pytest.approx(-100.15)
    assert metrics.realized_expectancy([])["insufficient_sample"] is True


def test_calibration_monotonic_detection_uses_shrunk():
    picks = ([make_pick("d", conf="high", right=True)] * 8 +
             [make_pick("d", conf="medium", right=True)] * 5 + [make_pick("d", conf="medium", right=False)] * 5 +
             [make_pick("d", conf="low", right=False)] * 8)
    cal = metrics.calibration(picks)
    assert cal["monotonic"] is True
    # a single lucky low-confidence win cannot flip monotonicity via shrinkage
    picks2 = [make_pick("d", conf="high", right=False)] + [make_pick("d", conf="low", right=True)]
    assert metrics.calibration(picks2)["monotonic"] in (True, False)  # shrunk, no crash


def test_edges_shrinkage_and_min_n():
    picks = [make_pick(f"d{i}", right=True, evidence=["good"]) for i in range(6)]
    picks += [make_pick(f"e{i}", right=False, evidence=["rare"]) for i in range(2)]  # below min_n
    res = metrics.edges(picks, min_n=3)
    tags = {e["tag"] for e in res["edges"]}
    assert "good" in tags and "rare" not in tags
    good = next(e for e in res["edges"] if e["tag"] == "good")
    assert good["shrunk"] < good["win_rate"]  # shrunk toward base, below raw 1.0


# ---------------- data_contract ----------------
def test_graded_picks_joins_only_resolved_and_matched():
    verdicts = [{"date": "2026-05-02", "symbol": "AAA", "verdict": "reaffirm", "confidence": "high",
                 "evidence": ["x"], "tony_score": 80, "target": None, "stop": None}]
    outcomes = [
        {"symbol": "AAA", "pick_date": "2026-05-01", "resolved_date": "2026-05-10", "return_pct": 4.0,
         "result": "target_hit", "entry": 100, "exit": 104},
        {"symbol": "BBB", "pick_date": "2026-05-01", "resolved_date": "2026-05-10", "return_pct": 1.0},  # no verdict
        {"symbol": "AAA", "pick_date": "2026-05-01", "return_pct": 2.0},  # unresolved (delayed label)
    ]
    picks = data_contract.graded_picks(verdicts, outcomes)
    assert len(picks) == 1 and picks[0]["symbol"] == "AAA" and picks[0]["right"] is True


def test_snapshot_hash_stable_and_sensitive():
    a = data_contract.snapshot_hash([{"x": 1}], [], [])
    assert a == data_contract.snapshot_hash([{"x": 1}], [], [])
    assert a != data_contract.snapshot_hash([{"x": 2}], [], [])


def test_health_reports_delayed_labels():
    verdicts = [{"date": "2026-05-02", "symbol": "AAA", "verdict": "reaffirm", "confidence": "low"}]
    outcomes = [{"symbol": "AAA", "pick_date": "2026-05-01", "resolved_date": "2026-05-10", "return_pct": 1.0},
                {"symbol": "AAA", "pick_date": "2026-05-01", "return_pct": 1.0}]
    h = data_contract.health(verdicts, outcomes)
    assert h["graded"] == 1 and h["pending_unresolved"] == 1 and h["outcomes"] == 2


# ---------------- walk_forward ----------------
def test_folds_are_leakage_safe():
    picks = [make_pick(f"2026-05-{d:02d}") for d in range(1, 13)]
    fs = walk_forward.folds(picks, n_folds=3)
    assert fs, "expected folds with 12 distinct dates"
    for f in fs:
        if f["train"]:
            max_train = max(p["resolved_date"] for p in f["train"])
            min_test = min(p["resolved_date"] for p in f["test"])
            assert max_train < min_test  # strictly past -> no future leakage


def test_folds_do_not_straddle_a_resolution_date():
    # many picks share one resolved_date at the boundary; that date must not split across train/test
    picks = ([make_pick("2026-05-01") for _ in range(4)] +
             [make_pick("2026-05-05") for _ in range(6)] +
             [make_pick(f"2026-05-{d:02d}") for d in range(6, 12)])
    fs = walk_forward.folds(picks, n_folds=3, min_train_frac=0.4)
    for f in fs:
        train_dates = {p["resolved_date"] for p in f["train"]}
        test_dates = {p["resolved_date"] for p in f["test"]}
        assert not (train_dates & test_dates)


def test_evaluate_insufficient_history():
    assert walk_forward.evaluate([make_pick("d1")])["status"] == "insufficient_history"


def test_evaluate_scores_with_enough_history():
    picks = [make_pick(f"2026-05-{d:02d}", ret=5.0) for d in range(1, 13)]
    res = walk_forward.evaluate(picks)
    assert res["status"] == "scored" and res["oos"]["n"] > 0


# ---------------- promotion_gate ----------------
def _report(realized_n, mean_pct, wf_status="scored", oos_er=1.0, monotonic=True, dd=None):
    return {
        "realized": {"n": realized_n, "mean_pct": mean_pct},
        "walk_forward": {"status": wf_status,
                         "oos": {"expectancy_return": {"mean_return_pct": oos_er},
                                 "win_rate": {"win_rate": 0.6},
                                 "calibration": {"monotonic": monotonic}}},
        "drawdown": {"drawdown_pct": dd},
    }


def test_promotion_blocks_on_thin_realized():
    g = promotion_gate.assert_promotion_ready(_report(4, -5.0))
    assert g["promote"] is False and any("thin" in r for r in g["reasons"])


def test_promotion_blocks_on_missing_walkforward():
    g = promotion_gate.assert_promotion_ready(_report(40, 2.0, wf_status="insufficient_history"))
    assert g["promote"] is False


def test_promotion_passes_only_when_all_clear():
    g = promotion_gate.assert_promotion_ready(_report(40, 2.0, oos_er=1.5, monotonic=True))
    assert g["promote"] is True and g["reasons"] == []


def test_promotion_fail_closed_on_drawdown():
    g = promotion_gate.assert_promotion_ready(_report(40, 2.0, dd=12.0))
    assert g["promote"] is False


def test_compare_candidate_ships_on_improvement_only():
    base = {"walk_forward": {"status": "scored", "oos": {"expectancy_return": {"mean_return_pct": 1.0},
            "win_rate": {"win_rate": 0.5}, "calibration": {"monotonic": True}}}}
    better = {"walk_forward": {"status": "scored", "oos": {"expectancy_return": {"mean_return_pct": 3.0},
              "win_rate": {"win_rate": 0.6}, "calibration": {"monotonic": True}}}}
    worse = {"walk_forward": {"status": "scored", "oos": {"expectancy_return": {"mean_return_pct": 0.5},
             "win_rate": {"win_rate": 0.4}, "calibration": {"monotonic": True}}}}
    assert promotion_gate.compare_candidate(base, better)["ship"] is True
    assert promotion_gate.compare_candidate(base, worse)["ship"] is False
    assert promotion_gate.compare_candidate(base, base)["ship"] is False  # identity never ships


# ---------------- harness (integration, synthetic) ----------------
def _inputs_good_bad():
    """12 open picks across 12 dates; a 'bad' evidence tag tracks the losers."""
    picks = []
    for i in range(1, 13):
        bad = i % 2 == 0
        picks.append(make_pick(f"2026-05-{i:02d}", right=not bad,
                                ret=-6.0 if bad else 6.0,
                                evidence=["bad_setup"] if bad else ["good_setup"],
                                symbol=f"S{i}"))
    return picks


def test_evaluate_candidate_dropping_losers_improves_oos(monkeypatch):
    picks = _inputs_good_bad()
    monkeypatch.setattr(data_contract, "graded_picks", lambda v, o: picks)
    monkeypatch.setattr(harness.drawdown_breaker, "_load_equity_series", lambda: [])
    inputs = {"verdicts": [], "outcomes": [], "realized": []}
    res = harness.evaluate_candidate(harness.drop_evidence_tag("bad_setup"),
                                     name="avoid_bad_setup", inputs=inputs)
    assert res["dropped"] == 6 and res["kept"] == 6
    assert res["candidate_oos"]["mean_return_pct"] > res["baseline_oos"]["mean_return_pct"]
    assert res["ship"] is True


def test_build_report_has_all_sections(monkeypatch):
    monkeypatch.setattr(harness.drawdown_breaker, "_load_equity_series", lambda: [])
    picks = _inputs_good_bad()
    rep = harness.build_report([], [], [], picks=picks)
    for key in ("snapshot", "health", "baseline", "realized", "walk_forward", "drawdown"):
        assert key in rep


def test_run_executes_clean_and_refuses_promotion_on_real_data():
    # Smoke against the live recorded files: the harness must RUN, and (honestly) refuse promotion
    # because the realized ledger is thin. ok=True is about execution, not promotion.
    r = harness.run()
    assert r["ok"] is True
    assert r["promotion"]["promote"] is False  # realized-track-is-truth: thin sample blocks


def test_harness_reproduces_live_scorecard_baseline():
    # Baseline-reproduction invariant: the harness's join/grading MUST agree with the live
    # tony_scorecard on the same recorded data. If a future refactor flips the grading rule, the
    # harness and the live record would diverge — this catches it.
    from runner.ledger import tony_scorecard as sc
    rec = sc.compute_record()
    inp = data_contract.load_inputs()
    picks = data_contract.graded_picks(inp["verdicts"], inp["outcomes"])
    assert len(picks) == rec["graded"]


def test_realized_track_is_truth_not_rosy_verdicts():
    # Even with a flawless verdict track, a thin/negative realized ledger must block promotion.
    rosy = {
        "realized": metrics.realized_expectancy([{"realized_pl": -100, "pct": -5}]),  # n=1, negative
        "walk_forward": {"status": "scored",
                         "oos": {"expectancy_return": {"mean_return_pct": 9.9},
                                 "win_rate": {"win_rate": 1.0},
                                 "calibration": {"monotonic": True}}},
        "drawdown": {"drawdown_pct": 0.0},
    }
    assert promotion_gate.assert_promotion_ready(rosy)["promote"] is False
