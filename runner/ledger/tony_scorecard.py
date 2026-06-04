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


def compute_record() -> dict:
    verdicts = _load(VERDICTS_FILE)
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return {"status": "awaiting_outcomes", "verdicts": len(verdicts), "graded": 0}

    graded = tony_right = 0
    agg = {"agreed_right": 0, "agreed_wrong": 0, "override_saved": 0, "override_missed": 0}
    conf_buckets: dict[str, list] = {"low": [], "medium": [], "high": []}

    for o in outcomes:  # one grade per RESOLVED pick (his final call before it closed)
        v = _matched_verdict(o, verdicts)
        if not v:
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


def write_record() -> dict:
    rec = compute_record()
    payload = json.dumps(rec, indent=2)
    for target in (RECORD_FILE, VAULT_RECORD_FILE):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
        except OSError as exc:
            _log.warning("write_record failed for %s: %s", target, exc)
    return rec
