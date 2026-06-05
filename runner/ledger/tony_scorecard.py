"""tony_scorecard — grades Tony's verdicts against the trading bot's outcomes.

Join key: (symbol, pick_date == the verdict's `date`). Grading rule:
  bullish (reaffirm/adjust) is RIGHT  if outcome return_pct > 0
  step-off (override/pass/close) is RIGHT if outcome return_pct <= 0  (correctly avoided a loser)

Produces the second track record + agreement matrix (Cockpit) and per-confidence
calibration. Degrades to status="awaiting_outcomes" when the bot hasn't emitted outcomes
yet — see docs/handoffs/2026-06-02-tony-loop-and-cockpit.md §4.
"""
import json
import logging
import math
import os
from pathlib import Path

_log = logging.getLogger(__name__)

_reports = Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"
_vault = Path(__file__).parent.parent.parent / "vault"
VERDICTS_FILE = Path(os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json")))
OUTCOMES_FILE = Path(os.environ.get("TONY_OUTCOMES_FILE", str(_reports / "tony_stocks_outcomes.json")))
RECORD_FILE = Path(os.environ.get("TONY_RECORD_FILE", str(_reports / "tony_stocks_record.json")))
# Tony's weekly self-review reads the record alongside his other vault files, so mirror it there too.
VAULT_RECORD_FILE = Path(os.environ.get("TONY_VAULT_RECORD_FILE", str(_vault / "tony-stocks" / "tony_stocks_record.json")))

_BULLISH = {"reaffirm", "adjust"}


def _load(p) -> list:
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def _is_right(verdict: str, ret: float) -> bool:
    return ret > 0 if verdict in _BULLISH else ret <= 0


def _matched_verdict(o: dict, verdicts: list) -> dict | None:
    """Match a resolved pick to Tony's verdict. Prefer a shared pick_id; otherwise range-join
    on symbol + verdict date within [pick_date, resolved_date], taking his LATEST (final) call.
    This survives entry_date != bridge_date and the fact that Tony only verdicts on Tier-1 days."""
    pid = o.get("pick_id")
    if pid:
        cands = [v for v in verdicts if v.get("pick_id") == pid]
    else:
        sym = o.get("symbol")
        pd = o.get("pick_date")
        rd = o.get("resolved_date")
        cands = [v for v in verdicts
                 if v.get("symbol") == sym and v.get("date")
                 and (not pd or v["date"] >= pd)
                 and (not rd or v["date"] <= rd)]
    return max(cands, key=lambda v: v.get("date", "")) if cands else None


# Agreement-block keys are the EXACT contract the bot's CommandCenterAgreement schema reads
# (schemas.py). Do not rename without coordinating: agreed_right, agreed_wrong,
# cc_overrode_saved, cc_overrode_missed.
def _empty_agreement() -> dict:
    return {"agreed_right": 0, "agreed_wrong": 0, "cc_overrode_saved": 0, "cc_overrode_missed": 0}


def compute_record() -> dict:
    verdicts = _load(VERDICTS_FILE)
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return {
            "status": "awaiting_outcomes",
            "verdicts": len(verdicts),
            "graded": 0,
            "win_rate": 0.0,
            "tony_win_rate": 0.0,
            "avg_pl_per_trade": None,
            "target_hits": 0,
            "stop_hits": 0,
            "agreement": _empty_agreement(),
            "calibration": {"low": None, "medium": None, "high": None},
        }

    graded = tony_right = target_hits = stop_hits = 0
    pl_values: list = []
    agg = _empty_agreement()
    conf_buckets: dict[str, list] = {"low": [], "medium": [], "high": []}

    for o in outcomes:  # one grade per RESOLVED pick (his final call before it closed)
        v = _matched_verdict(o, verdicts)
        if not v:
            continue
        graded += 1
        ret = float(o.get("return_pct", 0) or 0)
        if o.get("return_pct") is not None:
            pl_values.append(ret)
        result = o.get("result")
        if result == "target_hit":
            target_hits += 1
        elif result == "stop_hit":
            stop_hits += 1
        right = _is_right(v.get("verdict", ""), ret)
        tony_right += int(right)
        if v.get("verdict") in _BULLISH:
            agg["agreed_right" if ret > 0 else "agreed_wrong"] += 1
        else:
            agg["cc_overrode_saved" if ret <= 0 else "cc_overrode_missed"] += 1
        bucket = conf_buckets.get(v.get("confidence", "medium"))
        if bucket is not None:
            bucket.append(int(right))

    calibration = {
        k: round(sum(b) / len(b) * 100, 1) if b else None
        for k, b in conf_buckets.items()
    }
    win_rate = round(tony_right / graded * 100, 1) if graded else 0.0
    avg_pl = round(sum(pl_values) / len(pl_values), 2) if pl_values else None

    return {
        "status": "scored",
        "verdicts": len(verdicts),
        "graded": graded,
        "win_rate": win_rate,
        "tony_win_rate": win_rate,          # back-compat alias (tony_live_guard reads this)
        "avg_pl_per_trade": avg_pl,
        "target_hits": target_hits,
        "stop_hits": stop_hits,
        "agreement": agg,
        "calibration": calibration,
    }


def discover_edges(min_n: int = 5) -> dict:
    """Mine graded picks for evidence-tag → win-rate edges (>= min_n samples each)."""
    verdicts = _load(VERDICTS_FILE)
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return {"status": "insufficient_history", "edges": []}
    tally: dict[str, list] = {}
    for o in outcomes:
        v = _matched_verdict(o, verdicts)
        if not v:
            continue
        right = int(_is_right(v.get("verdict", ""), float(o.get("return_pct", 0) or 0)))
        for tag in v.get("evidence", []) or []:
            tally.setdefault(tag, []).append(right)
    edges = [
        {"tag": tag, "n": len(rs), "win_rate": round(sum(rs) / len(rs) * 100, 1)}
        for tag, rs in tally.items() if len(rs) >= min_n
    ]
    edges.sort(key=lambda e: -e["win_rate"])
    return {"status": "scored" if edges else "insufficient_history", "edges": edges}


_OPEN_VERDICTS = {"reaffirm", "adjust", "override"}  # the verdicts that become sized positions


def sizing_attribution() -> dict:
    """B1 honest-measurement: decompose Tony's realized return into picking vs sizing alpha,
    WITHOUT a second account. Realized return_pct is sizing-independent, so weighting each pick by
    its conviction multiplier and comparing to the equal-weight mean isolates what conviction
    sizing alone contributes. Lets B1 run in shadow (real sizing flat) and still be measured."""
    verdicts = _load(VERDICTS_FILE)
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return {"status": "awaiting_outcomes", "graded": 0, "picking_alpha_pct": None,
                "flat_return_pct": None, "conviction_return_pct": None, "sizing_alpha_pct": None}
    try:
        from runner.ledger.alpaca_paper import conviction_multiplier
    except Exception:
        def conviction_multiplier(_c):  # degrade to flat weighting if sizing module unavailable
            return 1.0
    rets, w_sum, w_ret, graded = [], 0.0, 0.0, 0
    for o in outcomes:
        v = _matched_verdict(o, verdicts)
        if not v or (v.get("verdict") or "").lower() not in _OPEN_VERDICTS:
            continue  # only entries get a conviction-scaled size
        ret = float(o.get("return_pct", 0) or 0)
        w = conviction_multiplier(v.get("confidence"))
        rets.append(ret)
        w_sum += w
        w_ret += w * ret
        graded += 1
    if not rets:
        return {"status": "awaiting_outcomes", "graded": 0, "picking_alpha_pct": None,
                "flat_return_pct": None, "conviction_return_pct": None, "sizing_alpha_pct": None}
    flat = sum(rets) / len(rets)
    conv = w_ret / w_sum if w_sum else flat
    # picking_alpha = selection quality at equal (flat) sizing; sizing_alpha = the extra from
    # conviction weighting. The execution-parity v1.1 §B.1 contract names these two explicitly.
    return {"status": "scored", "graded": graded,
            "picking_alpha_pct": round(flat, 3),
            "flat_return_pct": round(flat, 3),          # alias kept for the brief's wording
            "conviction_return_pct": round(conv, 3),
            "sizing_alpha_pct": round(conv - flat, 3)}


def _tony_equity_curve() -> list:
    """Tony's normalized equity series (indexed to 100, live-marked) for the head-to-head, pulled
    from equity_history. Best-effort: returns [] if the history isn't available yet."""
    try:
        from runner.ledger import equity_history
        pts = equity_history.curve().get("points", [])
        return [p["tony"] for p in pts if p.get("tony") is not None]
    except Exception as exc:
        _log.info("equity_curve for record unavailable: %s", exc)
        return []


def _sanitize(obj):
    """NaN/inf -> None: the bot's record reader requires strict-JSON-safe numbers."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def write_record() -> dict:
    rec = compute_record()
    rec["equity_curve"] = _tony_equity_curve()  # list[float], indexed to 100, live-marked
    rec["sizing_attribution"] = sizing_attribution()  # B1: picking vs sizing alpha (optional field)
    rec = _sanitize(rec)
    payload = json.dumps(rec, indent=2, allow_nan=False)
    for target in (RECORD_FILE, VAULT_RECORD_FILE):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
        except OSError as exc:
            _log.warning("write_record failed for %s: %s", target, exc)
    return rec
