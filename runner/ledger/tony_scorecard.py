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
import os
from pathlib import Path

_log = logging.getLogger(__name__)

_reports = Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"
VERDICTS_FILE = Path(os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json")))
OUTCOMES_FILE = Path(os.environ.get("TONY_OUTCOMES_FILE", str(_reports / "tony_stocks_outcomes.json")))
RECORD_FILE = Path(os.environ.get("TONY_RECORD_FILE", str(_reports / "tony_stocks_record.json")))

_BULLISH = {"reaffirm", "adjust"}


def _load(p) -> list:
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def _is_right(verdict: str, ret: float) -> bool:
    return ret > 0 if verdict in _BULLISH else ret <= 0


def compute_record() -> dict:
    verdicts = _load(VERDICTS_FILE)
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return {"status": "awaiting_outcomes", "verdicts": len(verdicts), "graded": 0}

    omap = {(o.get("symbol"), o.get("pick_date")): o for o in outcomes}
    graded = tony_right = 0
    agg = {"agreed_right": 0, "agreed_wrong": 0, "override_saved": 0, "override_missed": 0}
    conf_buckets: dict[str, list] = {"low": [], "medium": [], "high": []}

    for v in verdicts:
        o = omap.get((v.get("symbol"), v.get("date")))
        if not o:
            continue
        graded += 1
        ret = float(o.get("return_pct", 0) or 0)
        right = _is_right(v.get("verdict", ""), ret)
        tony_right += int(right)
        if v.get("verdict") in _BULLISH:
            agg["agreed_right" if ret > 0 else "agreed_wrong"] += 1
        else:
            agg["override_saved" if ret <= 0 else "override_missed"] += 1
        bucket = conf_buckets.get(v.get("confidence", "medium"))
        if bucket is not None:
            bucket.append(int(right))

    calibration = {
        k: round(sum(b) / len(b) * 100, 1) if b else None
        for k, b in conf_buckets.items()
    }

    return {
        "status": "scored",
        "verdicts": len(verdicts),
        "graded": graded,
        "tony_win_rate": round(tony_right / graded * 100, 1) if graded else 0.0,
        "agreement": agg,
        "calibration": calibration,
    }


def discover_edges(min_n: int = 5) -> dict:
    """Mine graded verdicts for evidence-tag → win-rate edges (>= min_n samples each)."""
    verdicts = _load(VERDICTS_FILE)
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return {"status": "insufficient_history", "edges": []}
    omap = {(o.get("symbol"), o.get("pick_date")): o for o in outcomes}
    tally: dict[str, list] = {}
    for v in verdicts:
        o = omap.get((v.get("symbol"), v.get("date")))
        if not o:
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


def write_record() -> dict:
    rec = compute_record()
    try:
        RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)
        RECORD_FILE.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    except OSError as exc:
        _log.warning("write_record failed: %s", exc)
    return rec
