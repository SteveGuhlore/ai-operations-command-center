"""harness — the walk-forward eval harness orchestrator (T1.1 keystone).

Two capabilities:
  * baseline()  — replay the FULL recorded history and reproduce the live record's calibration/
    edges, plus the realized (ground-truth) expectancy and the walk-forward out-of-sample view. This
    is the regression baseline every candidate must beat-or-match.
  * evaluate_candidate(rule) — the "would-this-change-help?" question. A candidate is expressed as a
    keep-predicate over picks (a learned rule of the form "stop taking setups like X"); the harness
    re-grades walk-forward on the trades that survive the rule and asks promotion_gate.compare_candidate
    whether out-of-sample expectancy improved with NO guardrail regression. Recorded replay only —
    no LLM re-runs (handoff §9 v1 scope).

Everything keys off RECORDED data and the REAL realized ledger; the verdict track is analysis only.
"""
import logging

from runner.eval import data_contract, metrics, walk_forward, promotion_gate
from runner.ledger import drawdown_breaker

_log = logging.getLogger(__name__)


def _full_metrics(picks: list) -> dict:
    return {
        "win_rate": metrics.win_rate(picks),
        "expectancy_return": metrics.expectancy_return(picks),
        "expectancy_r": metrics.expectancy_r(picks),
        "calibration": metrics.calibration(picks),
        "edges": metrics.edges(picks),
    }


def build_report(verdicts: list, outcomes: list, realized: list,
                 picks: list | None = None) -> dict:
    """Assemble one harness report from already-loaded inputs (pure-ish; only drawdown reads env
    defaults). `picks` lets a candidate pass an already-filtered set; defaults to the full join."""
    if picks is None:
        picks = data_contract.graded_picks(verdicts, outcomes)
    equity = drawdown_breaker._load_equity_series()
    return {
        "snapshot": data_contract.snapshot_hash(verdicts, outcomes, realized),
        "health": data_contract.health(verdicts, outcomes),
        "baseline": _full_metrics(picks),
        "realized": metrics.realized_expectancy(realized),
        "walk_forward": walk_forward.evaluate(picks),
        "drawdown": drawdown_breaker.breaker_state(realized, equity),
    }


def baseline() -> dict:
    """The live-data baseline report (reads the recorded files)."""
    inp = data_contract.load_inputs()
    return build_report(inp["verdicts"], inp["outcomes"], inp["realized"])


def evaluate_candidate(rule, name: str = "candidate", inputs: dict | None = None) -> dict:
    """`rule`: callable(pick)->bool, True = KEEP the position. Returns the comparison + both reports.
    A rule that keeps everything must read as 'no improvement' (identity → expectancy unchanged)."""
    inp = inputs or data_contract.load_inputs()
    verdicts, outcomes, realized = inp["verdicts"], inp["outcomes"], inp["realized"]
    all_picks = data_contract.graded_picks(verdicts, outcomes)
    try:
        kept = [p for p in all_picks if rule(p)]
    except Exception as exc:
        _log.warning("candidate rule %s raised: %s", name, exc)
        return {"name": name, "ship": False, "reasons": [f"rule error: {exc}"]}
    base_rep = build_report(verdicts, outcomes, realized, picks=all_picks)
    cand_rep = build_report(verdicts, outcomes, realized, picks=kept)
    cmp = promotion_gate.compare_candidate(base_rep, cand_rep)
    return {
        "name": name,
        "ship": cmp["ship"],
        "reasons": cmp["reasons"],
        "kept": len(kept),
        "dropped": len(all_picks) - len(kept),
        "baseline_oos": (base_rep["walk_forward"].get("oos") or {}).get("expectancy_return"),
        "candidate_oos": (cand_rep["walk_forward"].get("oos") or {}).get("expectancy_return"),
    }


# --- candidate-rule builders (common learned-rule shapes, evaluable on recorded data) ---
def drop_evidence_tag(tag: str):
    """A learned rule 'avoid setups carrying evidence tag <tag>'."""
    def keep(p):
        return tag not in (p.get("evidence") or [])
    return keep


def min_tony_score(threshold: float):
    """A learned rule 'only take picks with tony_score >= threshold'."""
    def keep(p):
        s = p.get("tony_score")
        try:
            return s is not None and float(s) >= threshold
        except (TypeError, ValueError):
            return False
    return keep


def run() -> dict:
    """Headless entrypoint for the master-always-deployable gate. Builds the baseline report and the
    fail-closed promotion verdict. `ok` is about the harness EXECUTING cleanly, not about promotion
    (promotion is correctly False while the realized sample is thin)."""
    try:
        rep = baseline()
        gate = promotion_gate.assert_promotion_ready(rep)
        return {"ok": True, "snapshot": rep["snapshot"], "health": rep["health"],
                "realized": rep["realized"], "walk_forward_status": rep["walk_forward"]["status"],
                "promotion": gate, "report": rep}
    except Exception as exc:
        _log.exception("harness run failed")
        return {"ok": False, "error": str(exc)}
