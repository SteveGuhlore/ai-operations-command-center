"""notify_policy — keep Tony's Telegram alerts INSTANT but quiet.

The operator firehose hit hundreds/day because reprice/ratchet pings fire per-position every
cycle a stop moves (see notify_reprice). This gate drops the redundant, low-value ones — exact
duplicates, immaterial micro-moves, and rapid repeats per symbol — while genuine events
(entries, exits) pass through untouched and instant. One case is ESCALATED, never suppressed:
the first move that puts a stop at/above entry (the position is now "risk-free") — the one
adjustment actually worth a buzz.

Fail-OPEN: any error here returns send=True, so a bug can never silence a real alert. Per-symbol
state persists in workspace/notify-reprice-state.json; tests inject ``now``.

Env knobs: TONY_REPRICE_COOLDOWN_MIN (default 90) · TONY_REPRICE_MIN_MOVE_PCT (default 0.75).
"""

import json
import logging
import os
import time
from pathlib import Path

_log = logging.getLogger(__name__)

STATE_FILE = (
    Path(__file__).parent.parent.parent / "workspace" / "notify-reprice-state.json"
)


def _cooldown_s() -> float:
    try:
        return max(0.0, float(os.environ.get("TONY_REPRICE_COOLDOWN_MIN", "90"))) * 60.0
    except (TypeError, ValueError):
        return 90 * 60.0


def _min_move_pct() -> float:
    try:
        return max(0.0, float(os.environ.get("TONY_REPRICE_MIN_MOVE_PCT", "0.75")))
    except (TypeError, ValueError):
        return 0.75


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _load() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def _save(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError as exc:
        _log.info("notify-reprice state write failed: %s", exc)


def gate_reprice(symbol, stop, target, entry=None, now=None) -> dict:
    """Decide whether a reprice ping for ``symbol`` should go out NOW.

    Returns ``{"send": bool, "lock": bool, "reason": str}``. ``lock`` is True only on the first
    move that puts the stop at/above entry (now risk-free) — always sent; the caller may swap in
    a special message. Anchors cooldown/materiality to the last NOTIFIED level (drops don't bump
    the anchor), so suppressed micro-moves still accumulate toward the next real ping.
    """
    try:
        now = time.time() if now is None else now
        sym = str(symbol or "").upper()
        s, t, e = _f(stop), _f(target), _f(entry)
        state = _load()
        prev = state.get(sym) or {}
        prev_s, prev_t = _f(prev.get("stop")), _f(prev.get("target"))
        was_locked = bool(prev.get("locked"))

        def _commit(locked: bool, reason: str) -> dict:
            state[sym] = {
                "stop": s,
                "target": t,
                "ts": now,
                "locked": locked or was_locked,
            }
            _save(state)
            return {"send": True, "lock": locked, "reason": reason}

        # 1) Breakeven lock — first time the stop reaches/exceeds entry. Escalate, never suppress.
        if e is not None and s is not None and s >= e and not was_locked:
            return _commit(True, "breakeven_lock")

        # 2) Exact duplicate — nothing changed since the last ping. Drop (don't bump the anchor).
        if (
            prev_s is not None
            and s is not None
            and round(prev_s, 2) == round(s, 2)
            and round(prev_t or 0, 2) == round(t or 0, 2)
        ):
            return {"send": False, "lock": False, "reason": "duplicate"}

        # 3) Immaterial — stop moved less than the threshold vs the last NOTIFIED level. Drop.
        if (
            prev_s
            and s is not None
            and abs(s - prev_s) / abs(prev_s) * 100.0 < _min_move_pct()
        ):
            return {"send": False, "lock": False, "reason": "immaterial"}

        # 4) Cooldown — too soon since the last ping for this symbol. Drop.
        if prev.get("ts") is not None and (now - float(prev["ts"])) < _cooldown_s():
            return {"send": False, "lock": False, "reason": "cooldown"}

        return _commit(False, "material_move")
    except (
        Exception
    ) as exc:  # fail-open: never silence a real alert because of a policy bug
        _log.info("notify_policy gate failed (fail-open): %s", exc)
        return {"send": True, "lock": False, "reason": "error_open"}
