"""telegram_inbox — inbound Telegram chat for Tony (the public-facing FACE).

Long-polls getUpdates with a persisted offset and routes each message by TIER:
  - operator (TELEGRAM_CHAT_ID): the full private cockpit, unmetered.
  - public (anyone else, when TONY_PUBLIC=on): read-only commands + buttons (free) and rate-limited,
    budget-capped natural-language Q&A (canned-FAQ first, then the LLM). Watchlist is operator-only.
READ-ONLY: chat reports and explains, it NEVER places, cancels, or modifies a trade. Fail-soft — a
network error, bad payload, or model failure is a no-op, never an exception into the cycle. The offset
advances only past updates we handled or intentionally skipped; a transient send failure stops
advancement so the reply is retried next poll.
"""
import json
import logging
import os
import threading
import time as _time
from pathlib import Path

import httpx

from runner.tools.notify import (notify, broadcast, inline_keyboard, answer_callback_query,
                                  edit_message_text, _channel)
from runner.tools import tony_voice as voice
from runner.tools import telegram_policy as policy

_log = logging.getLogger(__name__)
_API = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 35.0          # long-poll: must exceed the getUpdates server timeout below
_LONGPOLL = 25
_ON = {"on", "1", "true", "yes", "telegram"}
_RECORD_PAGE = 12
STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "telegram-inbox-state.json"

_MENU = inline_keyboard([[("📊 Status", "cmd:status"), ("📈 Record", "cmd:record")],
                         [("📖 Glossary", "cmd:glossary"), ("❓ Help", "cmd:help")]])


def _chat_enabled() -> bool:
    return _channel() == "telegram" and \
        os.environ.get("TONY_TELEGRAM_CHAT", "off").strip().lower() in _ON


def _public_enabled() -> bool:
    return os.environ.get("TONY_PUBLIC", "off").strip().lower() in _ON


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


# --- read-only data fetchers (formatting lives in tony_voice) ---------------------------------------

def _status_reply() -> str:
    from runner.ledger.alpaca_paper import account_record
    from runner.ledger.tony_realized import summary as realized_summary
    acct = account_record()
    if acct.get("status") != "ok":
        return "I can't read my book right this second — try me again in a minute."
    return voice.say_status(acct, realized_summary())


def _record_rows() -> list:
    from runner.ledger.tony_realized import records
    return records(newest_first=True)


def _realized_summary_safe() -> dict:
    from runner.ledger.tony_realized import summary as realized_summary
    try:
        return realized_summary()
    except Exception:
        return {}


def _record_reply(page: int = 0) -> dict:
    """Returns {'text', 'has_more', 'page'} for the paged /record view."""
    return voice.say_record_page(_record_rows(), _realized_summary_safe(),
                                 page=page, page_size=_RECORD_PAGE)


def _current_names(limit: int = 12) -> list:
    """Names Tony can actually talk about right now: open positions first (he's in them), then
    recently-verdicted symbols. Powers /explain discovery so the user never has to guess a ticker."""
    names: list = []
    try:
        from runner.ledger.alpaca_paper import account_record
        for p in account_record().get("open_positions", []) or []:
            s = (p.get("symbol") or "").upper()
            if s and s not in names:
                names.append(s)
    except Exception:
        pass
    try:
        from runner.tools.tony_verdict import VERDICTS_FILE
        verdicts = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
        for v in sorted(verdicts, key=lambda e: e.get("date", ""), reverse=True):
            s = (v.get("symbol") or "").upper()
            if s and s not in names:
                names.append(s)
            if len(names) >= limit:
                break
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        pass
    return names[:limit]


def _names_line(names: list) -> str:
    return ", ".join(f"<b>{n}</b>" for n in names)


def _ticker_writeup(symbol: str) -> str:
    """Tony's FULL per-ticker deep-dive from vault/tickers/<SYM>.md, lightly converted to Telegram
    HTML (notify() chunks it past 4096 chars). '' when there's no page. OPERATOR-ONLY — this
    forward-looking research must never leak to the public (front-running guard)."""
    import html
    sym = (symbol or "").upper()
    page = Path(__file__).parent.parent.parent / "vault" / "tickers" / f"{sym}.md"
    try:
        raw = page.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return ""
    if raw.startswith("---"):                       # drop YAML frontmatter
        parts = raw.split("---", 2)
        raw = parts[2] if len(parts) == 3 else raw
    out = []
    for line in raw.splitlines():
        s = line.rstrip()
        if not s.strip():
            out.append("")
            continue
        if s.lstrip().startswith("#"):
            out.append(f"<b>{html.escape(s.lstrip('#').strip())}</b>")
        else:
            body = s.lstrip()
            for bullet in ("*   ", "* ", "- "):
                if body.startswith(bullet):
                    body = "• " + body[len(bullet):]
                    break
            out.append(html.escape(body))
    return "\n".join(out).strip()


def _explain_reply(symbol: str, tier: str = "operator") -> str:
    names = _current_names()
    if not symbol:
        if names:
            return ("Pick one and I'll explain my thinking — I've got notes on "
                    f"{_names_line(names)}.\nLike <code>/explain {names[0]}</code>.")
        return voice.say_explain("", "", False)
    # Operator gets the FULL deep-dive write-up (notify() paginates it); the public stays on the
    # short verdict thesis so forward-looking research never leaks (front-running guard).
    if tier == "operator":
        writeup = _ticker_writeup(symbol)
        if writeup:
            return f"<b>{symbol.upper()} — my full write-up</b>\n\n{writeup}"
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
    if not thesis:
        msg = f"I don't have a fresh note on <b>{symbol.upper()}</b> yet."
        if names:
            msg += f" Here's what I'm in right now: {_names_line(names)} — try one of those."
        return msg
    return voice.say_explain(symbol, thesis, held)


def _record_markup(page: int, has_more: bool):
    buttons = []
    if page > 0:
        buttons.append(("◀ Newer", f"rec:{page - 1}"))
    if has_more:
        buttons.append((f"Show {_RECORD_PAGE} more ▶", f"rec:{page + 1}"))
    return inline_keyboard([buttons]) if buttons else None


# --- routing ---------------------------------------------------------------------------------------

def reply_for(text: str, tier: str = "operator", user_id: str = "") -> dict:
    """Route a text message to a reply payload {'text', 'reply_markup'?}. Read-only.
    Public tier: command allowlist (watchlist blocked) + FAQ + rate-limited NL fallback."""
    t = (text or "").strip()
    if not t:
        return {"text": voice.HELP, "reply_markup": _MENU}
    parts = t.split()
    is_cmd = t.startswith("/")
    cmd = parts[0].lower().lstrip("/").split("@")[0]
    arg = parts[1] if len(parts) > 1 else ""

    if is_cmd:
        if tier == "public" and not policy.command_allowed(cmd, "public"):
            return {"text": "That one's just for my operator — try <code>/status</code>, "
                            "<code>/record</code>, or <code>/explain SYM</code>.", "reply_markup": _MENU}
        if cmd in ("start", "help"):
            return {"text": voice.HELP, "reply_markup": _MENU}
        if cmd in ("status", "book"):
            return {"text": _status_reply(), "reply_markup": _MENU}
        if cmd in ("record", "stats"):
            page = _record_reply(0)
            return {"text": page["text"], "reply_markup": _record_markup(0, page["has_more"])}
        if cmd in ("explain", "why"):
            return {"text": _explain_reply(arg, tier), "reply_markup": _MENU}
        if cmd in ("glossary", "terms"):
            return {"text": voice.GLOSSARY, "reply_markup": _MENU}
        return {"text": ("I didn't catch that — try <code>/help</code> and I'll show you what I can "
                         "answer."), "reply_markup": _MENU}

    # --- free-text (natural language) ---
    # The canned FAQ is a PUBLIC-tier cost saver only; the operator's questions always reach the LLM
    # (a broad keyword like "what stocks" must never hijack a real operator question).
    if tier == "public":
        faq = policy.faq_answer(t)
        if faq:
            return {"text": faq, "reply_markup": _MENU}
        if not policy.allow_nl(user_id):
            return {"text": "I'm chatting with a lot of people right now — tap a button below or try "
                            "<code>/status</code> and I'll answer instantly.", "reply_markup": _MENU}
    from runner.tools.tony_synthesis import answer, synth_enabled
    if not synth_enabled():
        return {"text": "My live Q&amp;A is off right now — but I can still show you "
                        "<code>/status</code>, <code>/record</code>, or <code>/explain SYM</code>.",
                "reply_markup": _MENU}
    out = answer(t, public=(tier == "public"))
    if not out:
        return {"text": "I couldn't pull that together just now — ask me again, or tap "
                        "<code>/status</code> / <code>/record</code> / <code>/explain SYM</code>.",
                "reply_markup": _MENU}
    return {"text": out, "reply_markup": _MENU}


def _handle_callback(cb: dict) -> bool:
    """Handle a button tap. Returns True if a reply was sent (or intentionally finished)."""
    data = cb.get("data") or ""
    msg = cb.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    mid = msg.get("message_id")
    tier = policy.tier_for(chat)
    answer_callback_query(cb.get("id"))
    if tier == "public" and not _public_enabled():
        return True
    if data.startswith("rec:"):
        try:
            page = int(data.split(":", 1)[1])
        except ValueError:
            page = 0
        pg = _record_reply(page)
        res = edit_message_text(chat, mid, pg["text"],
                                reply_markup=_record_markup(page, pg["has_more"]))
        return bool(res.get("sent"))
    if data.startswith("cmd:"):
        rep = reply_for("/" + data.split(":", 1)[1], tier,
                        user_id=str((cb.get("from") or {}).get("id", "")))
        res = notify(rep["text"], chat_id=chat, reply_markup=rep.get("reply_markup"))
        return bool(res.get("sent"))
    return True


def _handle_update(u: dict):
    """Process one update. Returns (advance_ok, replied_count). advance_ok=False only on a transient
    send failure (so we retry); an intentionally-ignored update returns (True, 0)."""
    if "callback_query" in u:
        try:
            sent = _handle_callback(u["callback_query"])
            return (bool(sent), 1 if sent else 0)
        except Exception as exc:
            _log.info("telegram callback failed: %s", exc)
            return (True, 0)           # don't get wedged on a bad callback
    msg = u.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    user_id = str((msg.get("from") or {}).get("id", chat))
    text = msg.get("text", "")
    if not text:
        return (True, 0)               # non-text: skip, advance
    tier = policy.tier_for(chat)
    if tier == "public" and not _public_enabled():
        return (True, 0)               # public off: ignore strangers, still advance
    try:
        rep = reply_for(text, tier, user_id)
        res = notify(rep["text"], chat_id=chat, reply_markup=rep.get("reply_markup"))
        if not res.get("sent"):
            return (False, 0)          # transient send failure: stop advancing
        return (True, 1)
    except Exception as exc:
        _log.info("telegram reply failed: %s", exc)
        return (True, 0)               # logic error on this message: skip it, keep going


def poll_and_handle() -> dict:
    """One fetch+handle pass. Replies to the operator always (when chat on) and to the public when
    TONY_PUBLIC=on. Advances the offset only past handled/intentionally-skipped updates; a transient
    send failure stops advancement so the reply retries. Fail-soft no-op when disabled."""
    if not _chat_enabled():
        return {"handled": 0, "reason": "disabled"}
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    op_chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not op_chat:
        return {"handled": 0, "reason": "not_configured"}

    offset = _read_offset()
    try:
        r = httpx.get(
            _API.format(token=token, method="getUpdates"),
            params={"offset": offset, "timeout": _LONGPOLL,
                    "allowed_updates": json.dumps(["message", "callback_query"])},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        updates = r.json().get("result", []) or []
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("telegram getUpdates failed: %s", exc)
        return {"handled": 0, "reason": "fetch_failed"}

    handled = 0
    advance_to = offset - 1
    for u in sorted(updates, key=lambda x: int(x.get("update_id", 0))):
        uid = int(u.get("update_id", advance_to))
        ok, did_reply = _handle_update(u)
        if not ok:
            break                      # transient send failure: stop, retry this update next poll
        advance_to = uid
        handled += did_reply
    if advance_to >= offset:
        _write_offset(advance_to + 1)
    return {"handled": handled}


# --- background long-poll thread (fixes the ~3-min cycle latency) ----------------------------------

_POLLER_STARTED = False
_POLLER_THREAD = None
_poller_lock = threading.Lock()


def _poll_loop() -> None:
    while True:
        try:
            poll_and_handle()          # blocks up to ~_LONGPOLL via server-side long-poll
        except Exception as exc:       # belt-and-suspenders: the loop must never die
            _log.info("telegram poll loop error: %s", exc)
            _time.sleep(5)


def start_poller():
    """Start the single background long-poll thread (idempotent). No-op when chat is disabled."""
    global _POLLER_STARTED, _POLLER_THREAD
    with _poller_lock:
        if _POLLER_STARTED:
            return _POLLER_THREAD
        if not _chat_enabled():
            return None
        _POLLER_THREAD = threading.Thread(target=_poll_loop, name="tony-telegram-poll", daemon=True)
        _POLLER_THREAD.start()
        _POLLER_STARTED = True
        return _POLLER_THREAD
