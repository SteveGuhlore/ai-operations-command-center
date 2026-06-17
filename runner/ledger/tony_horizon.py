"""Tony's 2nd-pass revision of the bot's mechanical time-to-target horizon.

The BOT owns the mechanical baseline (`botHorizonDays`, computed from distance-to-target
over ATR(14) — see the trading-bot repo's analytics/horizon.py). Tony's job here is the
OVERRIDE: keep it, tighten it on conviction, or stand aside (null). We never invent a
calendar date — only inclusive trading-day ranges from now.

RESEARCH SIMULATION ONLY — these are heuristic estimates, not predictions or advice.
"""

from __future__ import annotations

# --- Mechanical baseline (mirror of trading-bot analytics/horizon.py — keep in sync) ---
# The bot brackets every pick as target = entry + 3.0*ATR and stop = entry - 1.5*ATR, so the
# scanner's target/stop spread alone recovers ATR(14) — CC needs no extra feed to size horizons.


def atr_from_levels(target, stop, *, k_target: float = 3.0, k_stop: float = 1.5):
    """Recover ATR(14) from the bot's bracket: ATR = (target - stop) / (k_target + k_stop).
    None when not derivable (missing or non-positive span)."""
    if target is None or stop is None:
        return None
    span = float(target) - float(stop)
    denom = k_target + k_stop
    if span <= 0 or denom <= 0:
        return None
    return span / denom


def bot_horizon_days(last, target, atr, realized_vol=None, *, max_days: int = 60):
    """Inclusive [min, max] trading-day range to target. None when target/atr unusable.
    MIRROR of trading-bot analytics/horizon.py:bot_horizon_days — keep the math identical.
    RESEARCH SIMULATION ONLY — a heuristic, not a prediction."""
    if target is None or atr is None or atr <= 0:
        return None
    dist = float(target) - float(last)
    if dist <= 0:
        return [1, 1]
    center = dist / atr  # ATRs of distance == trading days @ ~1 ATR/day
    atr_pct = (atr / last) if last > 0 else 0.0
    vol_adj = (realized_vol / atr_pct) if (realized_vol and atr_pct > 0) else 1.0
    w = max(0.20, min(0.80, 0.30 * vol_adj))
    lo = max(1, min(round(center * (1 - w)), max_days))
    hi = max(1, min(round(center * (1 + w)), max_days))
    if hi < lo:
        hi = lo
    return [int(lo), int(hi)]


# Verdicts where Tony is NOT carrying a live position toward a target → no active horizon.
_STAND_ASIDE = {"pass", "close"}

# How much Tony tightens (or loosens) the band around its center, by verdict × confidence.
# <1 narrows (more conviction), >1 widens. Center is preserved; only the half-width scales.
_TIGHTEN = {
    ("reaffirm", "low"): 1.10,
    ("reaffirm", "medium"): 1.00,
    ("reaffirm", "high"): 0.90,
    ("adjust", "low"): 0.85,
    ("adjust", "medium"): 0.70,
    ("adjust", "high"): 0.55,
    ("override", "low"): 0.85,
    ("override", "medium"): 0.70,
    ("override", "high"): 0.55,
}


def _center(rng) -> float | None:
    if not rng or len(rng) != 2:
        return None
    return (float(rng[0]) + float(rng[1])) / 2.0


def _scale_band(rng, factor: float, *, max_days: int = 60):
    """Scale the half-width of [lo,hi] by `factor`, keep the center, clamp to [1,max_days]."""
    lo, hi = float(rng[0]), float(rng[1])
    c = (lo + hi) / 2.0
    half = max((hi - lo) / 2.0 * factor, 0.5)
    nlo = max(1, round(c - half))
    nhi = min(max_days, round(c + half))
    if nhi < nlo:
        nhi = nlo
    return [int(nlo), int(nhi)]


def diverges(tony_range, bot_range, threshold: float = 0.5) -> bool:
    """True when Tony's center diverges from the bot's by more than `threshold` (fractional)."""
    ct, cb = _center(tony_range), _center(bot_range)
    if ct is None or cb is None or cb == 0:
        return False
    return abs(ct - cb) / abs(cb) > threshold


def revise_horizon(
    bot_range, verdict: str, *, confidence: str = "medium", tony_range=None
) -> dict:
    """Tony's revision of the bot's horizon.

    bot_range:   the bot's [min,max] trading-day range (or None if the bot had no target).
    verdict:     reaffirm | adjust | override | pass | close.
    confidence:  low | medium | high.
    tony_range:  Tony's own [min,max] if he set an independent target (else derived from bot_range).

    Returns {"horizonDays": [lo,hi] | None, "flagged": bool, "basis": str}.
    Standing aside (pass/close) → horizonDays None. No bot baseline and no own range → None.
    """
    v = (verdict or "").strip().lower()
    conf = (confidence or "medium").strip().lower()
    if conf not in ("low", "medium", "high"):
        conf = "medium"

    if v in _STAND_ASIDE:
        return {
            "horizonDays": None,
            "flagged": False,
            "basis": "standing aside — no active horizon",
        }

    base = tony_range if tony_range else bot_range
    if not base or len(base) != 2:
        return {"horizonDays": None, "flagged": False, "basis": ""}

    factor = _TIGHTEN.get((v, conf), 1.0)
    tony_h = _scale_band(base, factor)
    flagged = diverges(tony_h, bot_range, 0.5)

    if v == "reaffirm":
        basis = "kept the bot's horizon" + (
            "" if conf != "high" else " (high conviction)"
        )
    elif v == "adjust":
        basis = f"tightened on {conf} conviction"
    else:  # override
        basis = "own target" if tony_range else "tightened — own read"
    if flagged:
        basis += " · diverges >50% from bot"
    return {"horizonDays": tony_h, "flagged": flagged, "basis": basis}


def fmt_range(rng) -> str:
    """Human label for a trading-day range, e.g. [10,14] -> '10–14d'. None -> '—'."""
    if not rng or len(rng) != 2:
        return "—"
    lo, hi = int(rng[0]), int(rng[1])
    return f"{lo}d" if lo == hi else f"{lo}–{hi}d"


def build_projection(
    target,
    bot_range,
    verdict,
    *,
    confidence="medium",
    tony_range=None,
    basis_prefix: str = "",
) -> dict | None:
    """Assemble the dashboard `projection` object, or None when there is no usable target
    or Tony is standing aside. Backward-compatible: callers without a target get None."""
    if target is None:
        return None
    rev = revise_horizon(
        bot_range, verdict, confidence=confidence, tony_range=tony_range
    )
    if rev["horizonDays"] is None:
        return None
    basis = (basis_prefix + " · " if basis_prefix else "") + rev["basis"]
    return {
        "target": target,
        "botHorizonDays": list(bot_range) if bot_range else None,
        "horizonDays": rev["horizonDays"],
        "basis": basis.strip(" ·"),
        "flagged": rev["flagged"],
    }


def projection_for_verdict(
    last,
    verdict,
    *,
    scanner_target=None,
    scanner_stop=None,
    tony_target=None,
    tony_stop=None,
    confidence="medium",
) -> dict | None:
    """End-to-end projection for one verdict, deriving ATR from the bot's bracket.

    Uses Tony's own target when present, else the scanner's. Null-safe → None when
    standing aside or no usable target. RESEARCH SIMULATION ONLY.
    """
    bot_atr = atr_from_levels(scanner_target, scanner_stop)
    bot_range = bot_horizon_days(last, scanner_target, bot_atr) if bot_atr else None
    proj_target = tony_target if tony_target is not None else scanner_target
    tony_range = None
    if tony_target is not None and tony_stop is not None:
        t_atr = atr_from_levels(tony_target, tony_stop)
        tony_range = bot_horizon_days(last, tony_target, t_atr) if t_atr else None
    return build_projection(
        proj_target, bot_range, verdict, confidence=confidence, tony_range=tony_range
    )
