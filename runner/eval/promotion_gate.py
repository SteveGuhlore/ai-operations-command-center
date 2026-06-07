"""promotion_gate — fail-CLOSED release gate over a harness report.

A change may ship to real money only if it clears EVERY gate. The default posture is BLOCK: a
missing or insufficient metric is a block, never a pass (the audit lesson — a rosy unproven rule
must not slip through). The promotion axis is the REAL realized track; the verdict-track OOS
metrics are guardrails. With today's thin realized ledger this gate correctly refuses — that is the
honest answer, not a bug.
"""

# Defaults are deliberately conservative; T0.3 will replace them with data-modeled thresholds.
MIN_REALIZED = 30
MAX_DRAWDOWN_PCT = 8.0


def assert_promotion_ready(report: dict, *, min_realized: int = MIN_REALIZED,
                           require_monotonic: bool = True,
                           max_drawdown_pct: float = MAX_DRAWDOWN_PCT) -> dict:
    """Return {promote: bool, reasons: [...]}. promote is True only when reasons is empty."""
    reasons = []

    realized = report.get("realized") or {}
    rn = int(realized.get("n", 0) or 0)
    if rn < min_realized:
        reasons.append(f"realized sample too thin ({rn} < {min_realized} closed trades) — cannot prove expectancy")
    elif realized.get("mean_pct") is None or float(realized.get("mean_pct")) <= 0:
        reasons.append(f"realized expectancy not positive (mean_pct={realized.get('mean_pct')})")

    wf = report.get("walk_forward") or {}
    if wf.get("status") != "scored":
        reasons.append(f"walk-forward could not score ({wf.get('status', 'missing')})")
    else:
        oos = wf.get("oos") or {}
        er = (oos.get("expectancy_return") or {}).get("mean_return_pct")
        if er is None or float(er) <= 0:
            reasons.append(f"out-of-sample expectancy not positive (mean_return_pct={er})")
        cal = oos.get("calibration") or {}
        if require_monotonic and not cal.get("monotonic", False):
            reasons.append("out-of-sample calibration not monotonic (high>med>low)")

    dd = report.get("drawdown") or {}
    ddp = dd.get("drawdown_pct")
    if ddp is not None and float(ddp) >= max_drawdown_pct:
        reasons.append(f"current drawdown {ddp}% >= threshold {max_drawdown_pct}%")

    return {"promote": not reasons, "reasons": reasons}


def compare_candidate(baseline: dict, candidate: dict, *, tolerance: float = 0.0) -> dict:
    """The 'would-this-change-help?' decision. A candidate may promote only if it RAISES pooled OOS
    expectancy and regresses NO guardrail (calibration monotonicity, OOS win-rate) beyond tolerance.
    Fail-closed: if either side could not score out-of-sample, the answer is do-not-ship."""
    def oos(rep):
        wf = rep.get("walk_forward") or {}
        return (wf.get("oos") or {}) if wf.get("status") == "scored" else None

    b, c = oos(baseline), oos(candidate)
    if b is None or c is None:
        return {"improved": False, "ship": False,
                "reasons": ["walk-forward could not score baseline or candidate"]}

    def er(o):
        v = (o.get("expectancy_return") or {}).get("mean_return_pct")
        return float(v) if v is not None else None
    def wr(o):
        v = (o.get("win_rate") or {}).get("win_rate")
        return float(v) if v is not None else None

    reasons = []
    eb, ec = er(b), er(c)
    if eb is None or ec is None:
        reasons.append("missing OOS expectancy on one side")
    elif ec <= eb + tolerance:
        reasons.append(f"OOS expectancy did not improve ({ec} vs baseline {eb})")

    wb, wc = wr(b), wr(c)
    if wb is not None and wc is not None and wc < wb - tolerance:
        reasons.append(f"OOS win-rate regressed ({wc} vs baseline {wb})")

    cb = (b.get("calibration") or {}).get("monotonic", False)
    cc = (c.get("calibration") or {}).get("monotonic", False)
    if cb and not cc:
        reasons.append("candidate broke calibration monotonicity")

    return {"improved": not reasons, "ship": not reasons, "reasons": reasons}
