"""log_tony_idea — Tony's self-originated picks (Phase 5).

When Tony spots a name the scanner did NOT surface — a sector theme, post-earnings drift,
or a setup matching a pattern he wins on — he logs it here. Over time these are graded the
same way verdicts are, so the second layer stops only reacting to the bot and starts
originating. Writes tony_stocks_ideas.json beside the verdicts file.
"""

import logging
import os
from pathlib import Path

from runner.ledger._jsonio import atomic_write_json, load_list
from runner.ledger.market_clock import trading_day

_log = logging.getLogger(__name__)

_default = (
    Path(__file__).parent.parent.parent.parent
    / "TradingBotAgentProject"
    / "reports"
    / "tony_stocks_ideas.json"
)
IDEAS_FILE = Path(os.environ.get("TONY_IDEAS_FILE", str(_default)))

_SOURCES = {"sector_theme", "earnings_drift", "own_pattern", "news_catalyst", "other"}


def log_tony_idea(
    symbol: str,
    thesis: str,
    source: str = "other",
    score: float | None = None,
    catalysts: str = "",
) -> dict:
    sym = (symbol or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}
    src = (source or "other").strip().lower()
    if src not in _SOURCES:
        return {"error": f"source must be one of {sorted(_SOURCES)}"}
    entry = {
        "date": trading_day(),
        "symbol": sym,
        "thesis": thesis,
        "source": src,
        "score": round(float(score), 1) if score is not None else None,
        "catalysts": catalysts,
        "status": "new",
    }
    try:
        entries: list = load_list(IDEAS_FILE)
        entries = [
            e
            for e in entries
            if not (e.get("date") == entry["date"] and e.get("symbol") == sym)
        ]
        entries.append(entry)
        atomic_write_json(IDEAS_FILE, entries, indent=2)
        return {"success": True, "symbol": sym, "total_ideas": len(entries)}
    except OSError as exc:
        _log.warning("log_tony_idea failed: %s", exc)
        return {"error": str(exc)}


TOOL_SPEC = {
    "name": "log_tony_idea",
    "description": (
        "Log a stock idea the SCANNER did not surface but you think is worth watching — your "
        "own origination. Use when a sector theme, post-earnings drift, or a pattern you win on "
        "points at a name not in today's brief. source: sector_theme | earnings_drift | "
        "own_pattern | news_catalyst | other. Example: log_tony_idea(symbol='SMCI', "
        "thesis='AI-server demand + pulled back to SMA50 on light volume', source='own_pattern', "
        "score=72, catalysts='earnings 2026-06-18')"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "thesis": {"type": "string"},
            "source": {"type": "string", "enum": sorted(_SOURCES)},
            "score": {"type": "number", "description": "your 0-100 conviction"},
            "catalysts": {"type": "string"},
        },
        "required": ["symbol", "thesis"],
    },
}
