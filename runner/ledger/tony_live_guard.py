"""tony_live_guard — the gate any future real-money executor MUST pass. NO ORDER CODE.

Real-money execution is out of scope by design. This module exists so that when an executor
is eventually built, it cannot trade unless ALL of these hold:
  1. env TONY_LIVE_ENABLED is set (explicit operator opt-in), AND
  2. Tony has a real track record: >= MIN_GRADED graded verdicts AND win_rate >= MIN_WIN_RATE, AND
  3. the kill-switch file is absent.
Default state is DISABLED. This is a guardrail, not a feature.
"""
import os
from pathlib import Path

MIN_GRADED = 50
MIN_WIN_RATE = 60.0
KILL_SWITCH = Path(os.environ.get(
    "TONY_KILL_SWITCH",
    str(Path(__file__).parent.parent.parent / "workspace" / "TONY_LIVE_KILL"),
))


def live_allowed(record: dict) -> dict:
    """record = output of tony_scorecard.compute_record(). Returns {allowed, reasons}."""
    reasons = []
    if not os.environ.get("TONY_LIVE_ENABLED"):
        reasons.append("TONY_LIVE_ENABLED not set (operator opt-in required)")
    if KILL_SWITCH.exists():
        reasons.append("kill-switch file present")
    graded = int(record.get("graded", 0) or 0)
    win = float(record.get("tony_win_rate", 0) or 0)
    if graded < MIN_GRADED:
        reasons.append(f"track record too thin ({graded} < {MIN_GRADED} graded)")
    if win < MIN_WIN_RATE:
        reasons.append(f"win rate {win} < {MIN_WIN_RATE} required")
    return {"allowed": not reasons, "reasons": reasons}
