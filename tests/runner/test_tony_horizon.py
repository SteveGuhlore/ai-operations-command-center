"""Tony horizon math — the 2nd-pass revision of the bot's mechanical time-to-target.

Covers the handoff's required cases: inverse-ATR scaling, divergence>50% flag,
no-target → null, plus the bracket→ATR recovery CC uses to stay self-sufficient.
"""

from runner.ledger.tony_horizon import (
    atr_from_levels,
    bot_horizon_days,
    build_projection,
    diverges,
    projection_for_verdict,
    revise_horizon,
)


# --- mechanical baseline -------------------------------------------------------


def test_horizon_scales_inversely_with_atr():
    near = bot_horizon_days(100.0, 110.0, atr=5.0)  # 2 ATRs away
    far = bot_horizon_days(100.0, 110.0, atr=1.0)  # 10 ATRs away
    assert near is not None and far is not None
    # bigger ATR => fewer trading days to target (both ends)
    assert near[0] <= far[0]
    assert near[1] <= far[1]


def test_horizon_none_target_is_null():
    assert bot_horizon_days(100.0, None, atr=5.0) is None


def test_horizon_nonpositive_atr_is_null():
    assert bot_horizon_days(100.0, 110.0, atr=0.0) is None
    assert bot_horizon_days(100.0, 110.0, atr=-2.0) is None


def test_horizon_already_at_target():
    assert bot_horizon_days(110.0, 110.0, atr=5.0) == [1, 1]
    assert bot_horizon_days(120.0, 110.0, atr=5.0) == [1, 1]


def test_higher_realized_vol_widens_band():
    calm = bot_horizon_days(100.0, 130.0, atr=2.0, realized_vol=0.005)
    wild = bot_horizon_days(100.0, 130.0, atr=2.0, realized_vol=0.10)
    assert (wild[1] - wild[0]) >= (calm[1] - calm[0])


def test_horizon_clamped_to_bounds():
    rng = bot_horizon_days(100.0, 100000.0, atr=1.0, max_days=60)
    assert rng[0] >= 1 and rng[1] <= 60 and rng[1] >= rng[0]


def test_atr_from_levels_recovers_bracket():
    # target = entry + 3*ATR, stop = entry - 1.5*ATR  => ATR = (target-stop)/4.5
    entry, atr = 100.0, 4.0
    target, stop = entry + 3 * atr, entry - 1.5 * atr
    assert abs(atr_from_levels(target, stop) - atr) < 1e-9


def test_atr_from_levels_guards():
    assert atr_from_levels(None, 10.0) is None
    assert atr_from_levels(10.0, None) is None
    assert atr_from_levels(10.0, 10.0) is None  # zero span


# --- Tony's revision -----------------------------------------------------------


def test_reaffirm_keeps_bot_range():
    rev = revise_horizon([10, 14], "reaffirm")
    assert rev["horizonDays"] == [10, 14]
    assert rev["flagged"] is False


def test_adjust_tightens_band_same_center():
    rev = revise_horizon([10, 20], "adjust", confidence="high")
    lo, hi = rev["horizonDays"]
    # center preserved (15), band narrower than 10
    assert (hi - lo) < 10
    assert abs((lo + hi) / 2 - 15) <= 1


def test_stand_aside_is_null():
    assert revise_horizon([10, 14], "pass")["horizonDays"] is None
    assert revise_horizon([10, 14], "close")["horizonDays"] is None


def test_divergence_over_50pct_is_flagged():
    assert diverges([20, 28], [10, 14]) is True  # centers 24 vs 12
    assert diverges([11, 15], [10, 14]) is False  # centers 13 vs 12
    rev = revise_horizon([10, 14], "override", tony_range=[20, 28])
    assert rev["flagged"] is True


# --- projection assembly -------------------------------------------------------


def test_build_projection_null_safe():
    assert build_projection(None, [10, 14], "reaffirm") is None  # no target
    assert build_projection(110.0, [10, 14], "close") is None  # standing aside


def test_build_projection_shape():
    p = build_projection(110.0, [10, 14], "reaffirm")
    assert p["target"] == 110.0
    assert p["botHorizonDays"] == [10, 14]
    assert p["horizonDays"] == [10, 14]
    assert "flagged" in p and "basis" in p


def test_projection_for_verdict_from_scanner_bracket():
    # entry 100, ATR 4 => target 112, stop 94
    p = projection_for_verdict(
        100.0, "reaffirm", scanner_target=112.0, scanner_stop=94.0
    )
    assert p is not None
    assert p["target"] == 112.0
    assert p["botHorizonDays"] is not None and p["horizonDays"] is not None


def test_projection_for_verdict_no_target_is_null():
    assert projection_for_verdict(100.0, "reaffirm") is None


def test_projection_for_verdict_close_is_null():
    assert (
        projection_for_verdict(100.0, "close", scanner_target=112.0, scanner_stop=94.0)
        is None
    )
