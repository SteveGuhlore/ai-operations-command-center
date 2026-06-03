"""write_tony_verdict — Tony Stocks' structured pick/decision channel.

write_tony_insight is free-text commentary. THIS is the second-layer record: one
structured verdict per ticker Tony reviews — his own 0-100 score, his reaffirm/
adjust/override/pass/close decision on the scanner's pick, and his own plan. It is
the typed contract the Cockpit's dual-agent view + Track Record read, and the basis
for scoring Tony against the scanner over time. Lives beside agent_insights.json so
the trading-bot project / dashboard pick it up.
"""
import json
import logging
import os
from datetime import date
from pathlib import Path

_log = logging.getLogger(__name__)

_default_verdicts = (
    Path(__file__).parent.parent.parent.parent
    / "TradingBotAgentProject"
    / "reports"
    / "tony_stocks_verdicts.json"
)
VERDICTS_FILE = Path(os.environ.get("TONY_VERDICTS_FILE", str(_default_verdicts)))

_VERDICTS = {"reaffirm", "adjust", "override", "pass", "close"}


def write_tony_verdict(
    symbol: str,
    tony_score: float,
    verdict: str,
    thesis: str,
    scanner_score: float | None = None,
    target: float | None = None,
    stop: float | None = None,
    evidence: list | None = None,
    catalysts: str = "",
    earnings_date: str = "",
    confidence: str = "medium",
) -> dict:
    v = (verdict or "").strip().lower()
    if v not in _VERDICTS:
        return {"error": f"verdict must be one of {sorted(_VERDICTS)}, got '{verdict}'"}
    if v in ("adjust", "override"):
        if target is None or stop is None:
            return {"error": f"verdict '{v}' requires both target and stop (set YOUR own levels)"}
        if not float(target) > float(stop):
            return {"error": f"verdict '{v}' needs target > stop for a long bracket "
                             f"(got target={target}, stop={stop})"}
    sym = (symbol or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}
    try:
        score = float(tony_score)
    except (TypeError, ValueError):
        return {"error": "tony_score must be a number 0-100"}

    entry = {
        "date": str(date.today()),
        "symbol": sym,
        "tony_score": round(score, 1),
        "scanner_score": round(float(scanner_score), 2) if scanner_score is not None else None,
        "verdict": v,
        "thesis": thesis,
        "target": target,
        "stop": stop,
        "evidence": evidence or [],
        "catalysts": catalysts,
        "earnings_date": earnings_date,
        "confidence": confidence,
        "returned_pct": None,
        "schema_version": 1,
        "status": "new",
    }

    try:
        entries: list = []
        if VERDICTS_FILE.exists():
            try:
                entries = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                entries = []
        # One verdict per (date, symbol): replace same-day re-runs rather than stacking.
        entries = [e for e in entries if not (e.get("date") == entry["date"] and e.get("symbol") == sym)]
        entries.append(entry)
        VERDICTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        VERDICTS_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        return {"success": True, "symbol": sym, "verdict": v, "total_verdicts": len(entries)}
    except OSError as exc:
        _log.warning("write_tony_verdict failed: %s", exc)
        return {"error": str(exc)}


TOOL_SPEC = {
    "name": "write_tony_verdict",
    "description": (
        "Record your STRUCTURED second-layer decision on a ticker — this is your actual pick, "
        "not commentary (use write_tony_insight for commentary). Call it once per Tier-1 ticker "
        "after you have pulled get_stock_data and researched news. "
        "verdict: 'reaffirm' (agree with the scanner's pick), 'adjust' (agree but change "
        "target/stop/size), 'override' (you'd trade it differently than the scanner), "
        "'pass' (skip — not worth it), 'close' (exit/avoid). tony_score is YOUR independent "
        "0-100 conviction, formed from fundamentals + news + the setup — not a copy of the "
        "scanner's score. Always include the scanner_score so the two can be compared. "
        "Example: write_tony_verdict(symbol='GTLB', tony_score=78, scanner_score=75.01, "
        "verdict='adjust', target=29.0, stop=23.2, thesis='Strong rev growth + analyst upside, "
        "but earnings 6/10 inside the window — tighten target.', evidence=['rev_growth_28pct', "
        "'analyst_upside_12pct', 'earnings_in_window'], catalysts='Q2 earnings 2026-06-10', "
        "earnings_date='2026-06-10', confidence='high')"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol."},
            "tony_score": {"type": "number", "description": "YOUR independent 0-100 conviction."},
            "verdict": {"type": "string", "enum": ["reaffirm", "adjust", "override", "pass", "close"]},
            "thesis": {"type": "string", "description": "2-4 sentences: why this verdict, grounded in the data you pulled."},
            "scanner_score": {"type": "number", "description": "The scanner's score from the bridge, for comparison."},
            "target": {"type": "number", "description": "YOUR price target (may differ from the scanner's)."},
            "stop": {"type": "number", "description": "YOUR stop."},
            "evidence": {"type": "array", "items": {"type": "string"}, "description": "Short tags for the data points behind the call, e.g. ['rev_growth_28pct','analyst_upside_12pct']."},
            "catalysts": {"type": "string", "description": "Known upcoming catalyst(s), e.g. 'Q2 earnings 2026-06-10'."},
            "earnings_date": {"type": "string", "description": "Next earnings date YYYY-MM-DD if known."},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        },
        "required": ["symbol", "tony_score", "verdict", "thesis"],
    },
}
