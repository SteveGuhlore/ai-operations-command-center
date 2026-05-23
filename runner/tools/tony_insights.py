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
        "Write an AI-generated insight back to the Tony Stocks trading dashboard. "
        "Use this after analyzing a scan report to record your key findings. "
        "The insight will appear in the trading dashboard immediately."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "insight": {
                "type": "string",
                "description": "The insight text to display on the trading dashboard (1-3 sentences).",
            },
            "category": {
                "type": "string",
                "description": "Category of the insight.",
                "enum": ["momentum", "risk", "strategy", "watchlist", "general"],
            },
            "confidence": {
                "type": "string",
                "description": "Confidence level in this insight.",
                "enum": ["low", "medium", "high"],
            },
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ticker symbols this insight relates to (e.g. ['TSLA', 'AAPL']).",
            },
        },
        "required": ["insight"],
    },
}
