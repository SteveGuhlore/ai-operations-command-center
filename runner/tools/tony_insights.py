import json
import logging
import os
from datetime import date
from pathlib import Path

_log = logging.getLogger(__name__)

_default_insights = (
    Path(__file__).parent.parent.parent.parent
    / "TradingBotAgentProject"
    / "reports"
    / "agent_insights.json"
)
INSIGHTS_FILE = Path(os.environ.get("TONY_INSIGHTS_FILE", str(_default_insights)))


def write_tony_insight(
    insight: str,
    category: str = "general",
    confidence: str = "medium",
    symbols: list | None = None,
) -> dict:
    try:
        entries: list = []
        if INSIGHTS_FILE.exists():
            try:
                entries = json.loads(INSIGHTS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                entries = []

        entries.append({
            "date": str(date.today()),
            "category": category,
            "insight": insight,
            "confidence": confidence,
            "symbols": symbols or [],
            "status": "new",
        })

        INSIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        INSIGHTS_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        return {"success": True, "total_insights": len(entries)}
    except OSError as exc:
        _log.warning("write_tony_insight failed: %s", exc)
        return {"error": str(exc)}


TOOL_SPEC = {
    "name": "write_tony_insight",
    "description": (
        "Write an AI-generated insight to the Tony Stocks trading dashboard. "
        "Call this once per key finding after analyzing a scan report. "
        "The insight appears on the trading dashboard immediately. "
        "Example: write_tony_insight(insight='GTLB showing 4-day momentum continuation with XLK sector tailwind. High conviction for Tuesday open if tech sector opens flat-to-up.', category='momentum', confidence='high', symbols=['GTLB'])"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "insight": {
                "type": "string",
                "description": (
                    "The full insight text (2-4 sentences). Include: ticker(s), signal type, "
                    "catalyst found, and your conviction reasoning. "
                    "Example: 'GTLB has held a momentum continuation setup for 4 consecutive days. "
                    "No negative news found. Enterprise SaaS sector strength confirmed by XLK trend. "
                    "High conviction for Tuesday open — watch first 5-min candle for confirmation.'"
                ),
            },
            "category": {
                "type": "string",
                "description": (
                    "momentum = bullish signal or continuation. "
                    "risk = exit watch, weakening, or macro threat. "
                    "strategy = sector context or positioning advice. "
                    "watchlist = pre-trigger ticker observation. "
                    "general = other."
                ),
                "enum": ["momentum", "risk", "strategy", "watchlist", "general"],
            },
            "confidence": {
                "type": "string",
                "description": "high = multi-day signal + news catalyst. medium = signal only. low = pattern only.",
                "enum": ["low", "medium", "high"],
            },
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ticker symbols this insight covers. Example: ['GTLB'] or ['BKR', 'SLB', 'XLE'].",
            },
        },
        "required": ["insight", "category", "confidence", "symbols"],
    },
}
