"""tony_nudges — Tony texts first. Proactive, de-duped, public-safe notes to the channel + operator:
a new equity high and an end-of-day sign-off. Entry/exit heads-ups already ride notify_entry/exit.
Read-only and fail-soft; gated by TONY_PUBLIC (broadcast) + TONY_NOTIFY (operator). De-dup via a small
state file so a note fires at most once per event/day."""
import json
import logging
from pathlib import Path

from runner.tools.notify import notify, broadcast

_log = logging.getLogger(__name__)
STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "nudge-state.json"


def _load() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def _save(d: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(d), encoding="utf-8")
    except OSError as exc:
        _log.info("nudge state write failed: %s", exc)


def _tony_equity():
    from runner.ledger.alpaca_paper import account_record
    acct = account_record()
    eq = acct.get("equity") if acct.get("status") == "ok" else None
    try:
        return float(eq) if eq is not None else None
    except (TypeError, ValueError):
        return None


def _prev_peak():
    return _load().get("equity_peak")


def _daily_wrap_text() -> str:
    from runner.tools.tony_synthesis import daily_wrap, synth_enabled
    if synth_enabled():
        txt = daily_wrap()
        if txt:
            return txt
    from runner.ledger.alpaca_paper import account_record
    from runner.tools.tony_voice import say_daily_header
    acct = account_record()
    return say_daily_header(acct.get("equity") if acct.get("status") == "ok" else None)


def _send_both(text: str) -> dict:
    b = broadcast(text)
    notify(text)                       # operator copy (own chat)
    return {"sent": bool(b.get("sent"))}


def maybe_equity_high() -> dict:
    """Fire once when Tony's equity sets a new high-water mark."""
    eq = _tony_equity()
    if eq is None:
        return {"sent": False, "reason": "no_equity"}
    peak = _prev_peak()
    try:
        peak_f = float(peak) if peak is not None else None
    except (TypeError, ValueError):
        peak_f = None
    if peak_f is not None and eq <= peak_f:
        return {"sent": False, "reason": "no_new_high"}
    st = _load()
    st["equity_peak"] = eq
    _save(st)
    if peak_f is None:                 # first observation: record the mark, don't shout
        return {"sent": False, "reason": "first_mark"}
    return _send_both(f"🚀 <b>New high.</b> My account just set a fresh record at "
                      f"${eq:,.0f}. Onward — I'll keep risking small and letting winners run.")


def maybe_eod_signoff(day: str) -> dict:
    """Fire once per market day: a plain-English wrap to the channel + operator."""
    st = _load()
    if st.get("eod_day") == day:
        return {"sent": False, "reason": "already"}
    text = _daily_wrap_text()
    if not text:
        return {"sent": False, "reason": "no_text"}
    st["eod_day"] = day
    _save(st)
    return _send_both("🌙 <b>That's a wrap on my day.</b>\n" + text + _day_ledger_text(day))


def _day_ledger_text(day: str) -> str:
    """Deterministic list of today's closed trades — appended under the LLM prose so the wrap
    ALWAYS shows what was sold (the narrative model may gloss over exits). Fail-soft to ''."""
    try:
        from runner.ledger.tony_realized import records, summary
        from runner.tools.tony_voice import say_day_ledger
        rows = [r for r in records() if r.get("date") == day]
        return say_day_ledger(rows, (summary() or {}).get("today", {}))
    except Exception as exc:
        _log.info("day ledger build failed: %s", exc)
        return ""
