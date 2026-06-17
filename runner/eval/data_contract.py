"""data_contract — the eval harness's typed view over Tony's recorded history.

Entity grain: one verdict per (symbol, pick_date). Labels are DELAYED — outcomes resolve days
after the pick, so only RESOLVED picks are graded. Walk-forward ordering is by `resolved_date`,
never verdict `date`: the verdicts file is flushed each session and carries no temporal spread,
so the resolution timeline is the only honest axis for a train-past / test-future split.

The join + grading rule are imported verbatim from tony_scorecard so the harness REPRODUCES the
live record exactly (baseline-reproduction requirement). NO LEAKAGE happens here — this module only
labels picks; the walk-forward splitter is what guarantees nothing trains on a future outcome.
"""
import hashlib
import json
import logging

from runner.ledger import tony_scorecard as sc
from runner.ledger import tony_realized

_log = logging.getLogger(__name__)


def load_inputs() -> dict:
    """Fail-soft read of the three recorded sources. Returns {verdicts, outcomes, realized}."""
    return {
        "verdicts": sc._load(sc.VERDICTS_FILE),
        "outcomes": sc._load(sc.OUTCOMES_FILE),
        "realized": tony_realized._load(),
    }


def snapshot_hash(verdicts: list, outcomes: list, realized: list) -> str:
    """Stable sha256 over the three inputs so every harness run is reproducible/versioned."""
    blob = json.dumps([verdicts, outcomes, realized], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def graded_picks(verdicts: list, outcomes: list) -> list:
    """One labeled record per RESOLVED outcome that matches a verdict. The label (`right`) and the
    join use tony_scorecard's live rule verbatim. Picks without a resolved_date or without a matched
    verdict are excluded (they are not yet gradable — delayed labels)."""
    out = []
    for o in outcomes:
        resolved = o.get("resolved_date")
        if not resolved:
            continue
        v = sc._matched_verdict(o, verdicts)
        if not v:
            continue
        try:
            ret = float(o.get("return_pct", 0) or 0)
        except (TypeError, ValueError):
            # One malformed recorded outcome must not abort the whole harness —
            # skip the bad row and keep grading the rest.
            _log.warning("graded_picks: skipping outcome with bad return_pct: %r", o.get("symbol"))
            continue
        out.append({
            "symbol": o.get("symbol"),
            "pick_date": o.get("pick_date"),
            "resolved_date": resolved,
            "verdict": v.get("verdict", ""),
            "confidence": (v.get("confidence") or "medium"),
            "evidence": list(v.get("evidence") or []),
            "return_pct": ret,
            "result": o.get("result"),
            "right": sc._is_right(v.get("verdict", ""), ret),
            "tony_score": v.get("tony_score"),
            "entry": o.get("entry"),
            "exit": o.get("exit"),
            "days_held": o.get("days_held"),
            "target": v.get("target"),
            "stop": v.get("stop"),
        })
    return out


def order_by_resolution(picks: list) -> list:
    """Chronological by resolution — the only leakage-safe axis for walk-forward (delayed labels)."""
    return sorted(picks, key=lambda p: (str(p.get("resolved_date") or ""), str(p.get("symbol") or "")))


def health(verdicts: list, outcomes: list) -> dict:
    """Delayed-label health: how much of the recorded history is actually gradable yet."""
    graded = graded_picks(verdicts, outcomes)
    pending = sum(1 for o in outcomes if not o.get("resolved_date"))
    res_dates = sorted(p["resolved_date"] for p in graded if p.get("resolved_date"))
    return {
        "verdicts": len(verdicts),
        "outcomes": len(outcomes),
        "graded": len(graded),
        "pending_unresolved": pending,
        "resolved_pct": round(len(graded) / len(outcomes) * 100, 1) if outcomes else 0.0,
        "resolution_span": [res_dates[0], res_dates[-1]] if res_dates else [None, None],
    }
