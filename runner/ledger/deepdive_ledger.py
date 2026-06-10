"""Per-symbol deep-dive cooldown — so the research fan-out covers the BREADTH of the universe
instead of re-grading the same handful every bridge. A name is eligible for a fresh deep-dive
only once it's off the cooldown window (default 4h): it CAN be re-graded later in the day on
fresh data, just not 'the same ones over and over'. Fail-soft — degrades to 'due' so a ledger
problem never starves research.
"""
import json
import os
from datetime import datetime
from pathlib import Path

LEDGER_FILE = Path(os.environ.get(
    "TONY_DEEPDIVE_LEDGER_FILE",
    str(Path(__file__).parent.parent.parent / "workspace" / "deepdive-ledger.json"),
))
COOLDOWN_HOURS = float(os.environ.get("TONY_DEEPDIVE_COOLDOWN_HOURS", "4"))


def _read() -> dict:
    try:
        data = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def due_for_deepdive(symbol: str, cooldown_hours: float | None = None) -> bool:
    """True if `symbol` has never been deep-dived or its last deep-dive is older than the cooldown."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return False
    last = _read().get(sym)
    if not last:
        return True
    try:
        elapsed = datetime.now() - datetime.fromisoformat(last)
    except (ValueError, TypeError):
        return True
    cd = COOLDOWN_HOURS if cooldown_hours is None else cooldown_hours
    return elapsed.total_seconds() >= cd * 3600


def mark_deepdived(symbol: str) -> None:
    sym = (symbol or "").strip().upper()
    if not sym:
        return
    data = _read()
    data[sym] = datetime.now().isoformat()
    try:
        LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
        LEDGER_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
