"""metrics — deterministic code graders for the eval harness.

Every metric is a pure function over a list of graded-pick dicts (see data_contract.graded_picks)
or realized-ledger rows. Two expectancy views are reported, and the distinction is load-bearing:
  * return/R expectancy over the VERDICT track (verdict-vs-bot-outcome) — analysis only, ROSY.
  * realized expectancy over the REAL Alpaca-reconciled ledger — GROUND TRUTH, the promotion axis.
Small samples are never trusted raw: edge win-rates carry Wilson confidence intervals AND a
Bayesian (Beta) shrinkage toward the base rate, which kills the old min_n=5 over-trust (T1.6).
"""
import math

from runner.ledger.tony_scorecard import _OPEN_VERDICTS

_Z = 1.96  # 95% normal quantile


def wilson_interval(k: int, n: int, z: float = _Z) -> tuple:
    """95% Wilson score interval for a binomial proportion (well-behaved at small n / extremes)."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (round(max(0.0, center - half), 4), round(min(1.0, center + half), 4))


def shrink(k: int, n: int, base: float, strength: float = 4.0) -> float:
    """Beta-posterior mean shrinking k/n toward `base` with `strength` pseudo-observations.
    A 5/5 sample (raw 1.0) at base 0.5, strength 4 -> (5+2)/(5+4)=0.78, not 1.0 — the anti-fluke."""
    if n < 0 or strength < 0:
        return base
    return (k + base * strength) / (n + strength)


def _open(picks: list) -> list:
    return [p for p in picks if (p.get("verdict") or "").lower() in _OPEN_VERDICTS]


def win_rate(picks: list) -> dict:
    """Fraction of graded picks Tony got right (same rule as the live scorecard)."""
    n = len(picks)
    k = sum(1 for p in picks if p.get("right"))
    return {"n": n, "wins": k, "win_rate": round(k / n, 4) if n else None,
            "ci": wilson_interval(k, n) if n else None}


def expectancy_return(picks: list) -> dict:
    """Mean return_pct over Tony's ENTRY verdicts (positions) — VERDICT track, analysis only."""
    opens = _open(picks)
    rets = [float(p.get("return_pct", 0) or 0) for p in opens]
    if not rets:
        return {"n": 0, "mean_return_pct": None}
    return {"n": len(rets), "mean_return_pct": round(sum(rets) / len(rets), 4)}


def _r_multiple(entry, exit_price, stop) -> float | None:
    try:
        en, ex, st = float(entry), float(exit_price), float(stop)
    except (TypeError, ValueError):
        return None
    risk = en - st
    if risk <= 0:
        return None
    return (ex - en) / risk


def expectancy_r(picks: list) -> dict:
    """Mean R-multiple over entry verdicts where a stop is recoverable — VERDICT track, analysis."""
    rs = []
    for p in _open(picks):
        r = _r_multiple(p.get("entry"), p.get("exit"), p.get("stop"))
        if r is not None:
            rs.append(r)
    if not rs:
        return {"n": 0, "mean_r": None}
    return {"n": len(rs), "mean_r": round(sum(rs) / len(rs), 4)}


def realized_expectancy(realized_rows: list) -> dict:
    """GROUND TRUTH: mean realized pct + total $ over actually-closed trades. The promotion axis.
    Flags insufficient_sample so a 4-trade ledger can never read as a proven expectancy."""
    rows = [r for r in realized_rows if r.get("realized_pl") is not None]
    n = len(rows)
    if not n:
        return {"n": 0, "mean_pct": None, "total_pl": 0.0, "wins": 0,
                "win_rate": None, "insufficient_sample": True}
    pcts = [float(r.get("pct", 0) or 0) for r in rows]
    wins = sum(1 for r in rows if float(r.get("realized_pl", 0) or 0) > 0)
    return {
        "n": n,
        "mean_pct": round(sum(pcts) / n, 4),
        "total_pl": round(sum(float(r.get("realized_pl", 0) or 0) for r in rows), 2),
        "wins": wins,
        "win_rate": round(wins / n, 4),
        "insufficient_sample": n < 30,
    }


_CONF_ORDER = ["high", "medium", "low"]


def calibration(picks: list) -> dict:
    """Per-confidence win-rate (raw + shrunk + Wilson CI) and whether it's MONOTONIC high>med>low.
    Monotonicity uses the shrunk means so a 1-sample bucket can't manufacture a false ordering."""
    base = (sum(1 for p in picks if p.get("right")) / len(picks)) if picks else 0.5
    buckets: dict[str, dict] = {}
    for c in _CONF_ORDER:
        b = [p for p in picks if (p.get("confidence") or "medium").lower() == c]
        n, k = len(b), sum(1 for p in b if p.get("right"))
        buckets[c] = {
            "n": n,
            "win_rate": round(k / n, 4) if n else None,
            "shrunk": round(shrink(k, n, base), 4) if n else None,
            "ci": wilson_interval(k, n) if n else None,
        }
    sh = [buckets[c]["shrunk"] for c in _CONF_ORDER]
    monotonic = all(a is not None and b is not None and a >= b for a, b in zip(sh, sh[1:]))
    return {"base_rate": round(base, 4), "buckets": buckets, "monotonic": monotonic}


def edges(picks: list, min_n: int = 3, strength: float = 4.0) -> dict:
    """Evidence-tag -> win-rate edges with Bayesian shrinkage + Wilson CIs (T1.6). Reported edges
    are SORTED by shrunk win-rate; the raw rate and CI are kept so a thin edge can't be over-trusted."""
    base = (sum(1 for p in picks if p.get("right")) / len(picks)) if picks else 0.5
    tally: dict[str, list] = {}
    for p in picks:
        right = int(bool(p.get("right")))
        for tag in p.get("evidence") or []:
            tally.setdefault(tag, []).append(right)
    out = []
    for tag, rs in tally.items():
        n, k = len(rs), sum(rs)
        if n < min_n:
            continue
        lo, hi = wilson_interval(k, n)
        out.append({"tag": tag, "n": n, "win_rate": round(k / n, 4),
                    "shrunk": round(shrink(k, n, base, strength), 4),
                    "ci_low": lo, "ci_high": hi})
    out.sort(key=lambda e: -e["shrunk"])
    return {"base_rate": round(base, 4), "edges": out}
