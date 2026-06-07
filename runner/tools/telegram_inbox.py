"""telegram_inbox — inbound Telegram chat for Tony (Phase 2, two-way).

Long-polls Telegram getUpdates with a persisted offset, **whitelisted to TELEGRAM_CHAT_ID only**
(a bot token is semi-public, so we answer the operator and silently ignore everyone else), and routes
slash-commands to first-person replies via tony_voice. READ-ONLY: chat reports and explains, it NEVER
places, cancels, or modifies a trade. Opt-in (TONY_TELEGRAM_CHAT=on) and fail-soft — a network error
or bad payload is a no-op, never an exception into the cycle.
"""
import json
import logging
import os
from pathlib import Path

import httpx

from runner.tools.notify import _channel, notify
from runner.tools import tony_voice as voice

_log = logging.getLogger(__name__)
_API = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 12.0
_ON = {"on", "1", "true", "yes", "telegram"}
STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "telegram-inbox-state.json"


def _enabled() -> bool:
    return _channel() == "telegram" and \
        os.environ.get("TONY_TELEGRAM_CHAT", "off").strip().lower() in _ON


def _read_offset() -> int:
    try:
        return int(json.loads(STATE_FILE.read_text(encoding="utf-8")).get("offset", 0))
    except (json.JSONDecodeError, OSError, FileNotFoundError, ValueError, TypeError):
        return 0


def _write_offset(offset: int) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"offset": offset}), encoding="utf-8")
    except OSError as exc:
        _log.info("telegram offset write failed: %s", exc)


# --- command data fetchers (thin; formatting lives in tony_voice) ----------------------------------

def _status_reply() -> str:
    from runner.ledger.alpaca_paper import account_record
    from runner.ledger.tony_realized import summary as realized_summary
    acct = account_record()
    if acct.get("status") != "ok":
        return "I can't read my book right this second — try me again in a minute."
    return voice.say_status(acct, realized_summary())


def _record_reply() -> str:
    from runner.ledger.tony_scorecard import compute_record, discover_edges
    from runner.ledger.tony_realized import summary as realized_summary
    return voice.say_record(compute_record(), discover_edges(), realized_summary())


def _explain_reply(symbol: str) -> str:
    if not symbol:
        return voice.say_explain("", "", False)
    from runner.ledger.alpaca_paper import _verdict_thesis, account_record
    from runner.tools.tony_verdict import VERDICTS_FILE
    try:
        verdicts = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        verdicts = []
    thesis = _verdict_thesis(verdicts, symbol)
    held = False
    try:
        acct = account_record()
        held = any((p.get("symbol") or "").upper() == symbol.upper()
                   for p in acct.get("open_positions", []) or [])
    except Exception:
        pass
    return voice.say_explain(symbol, thesis, held)


def reply_for(text: str) -> str:
    """Route a message to Tony's reply. Pure given the data fetchers; the fetchers are read-only."""
    t = (text or "").strip()
    if not t:
        return voice.HELP
    parts = t.split()
    cmd = parts[0].lower().lstrip("/").split("@")[0]  # tolerate /cmd@BotName in groups
    arg = parts[1] if len(parts) > 1 else ""
    if cmd in ("start", "help"):
        return voice.HELP
    if cmd in ("status", "book"):
        return _status_reply()
    if cmd in ("record", "stats"):
        return _record_reply()
    if cmd in ("explain", "why"):
        return _explain_reply(arg)
    if cmd in ("glossary", "terms"):
        return voice.GLOSSARY
    return ("I didn't catch that — I only know a few commands. Try <code>/help</code> "
            "and I'll show you what I can answer.")


def poll_and_handle() -> dict:
    """Fetch new messages and reply to the whitelisted operator. Fail-soft no-op when disabled."""
    if not _enabled():
        return {"handled": 0, "reason": "disabled"}
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return {"handled": 0, "reason": "not_configured"}

    offset = _read_offset()
    try:
        r = httpx.get(
            _API.format(token=token, method="getUpdates"),
            params={"offset": offset, "timeout": 0,
                    "allowed_updates": json.dumps(["message"])},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        updates = r.json().get("result", []) or []
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("telegram getUpdates failed: %s", exc)
        return {"handled": 0, "reason": "fetch_failed"}

    handled = 0
    max_id = offset - 1
    for u in updates:
        max_id = max(max_id, int(u.get("update_id", max_id)))
        msg = u.get("message") or {}
        msg_chat = str((msg.get("chat") or {}).get("id", ""))
        text = msg.get("text", "")
        if msg_chat != str(chat) or not text:
            continue  # whitelist + ignore non-text
        try:
            notify(reply_for(text))
            handled += 1
        except Exception as exc:
            _log.info("telegram reply failed: %s", exc)
    if updates:
        _write_offset(max_id + 1)  # advance past everything we saw, even ignored senders
    return {"handled": handled}
