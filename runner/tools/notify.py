"""notify — push Tony's trade events to the operator's phone (CC-internal, cosmetic).

This is a one-way outbound notifier so the operator can watch Tony from work. It touches
NOTHING in the bot<->CC contract — it only reads Tony's own execution events and sends a
Telegram message. Config-gated and fail-soft: a missing token or a network error degrades to
a silent no-op so a notification can NEVER block or break a trade.

Env: TONY_NOTIFY=telegram|off (default off) · TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID
(a private chat id, or a group/supergroup id — usually negative — to post to a group).
"""
import logging
import os

import httpx

_log = logging.getLogger(__name__)

_TG_URL = "https://api.telegram.org/bot{token}/sendMessage"
_TIMEOUT = 10.0
_OFF = {"", "off", "0", "false", "no"}


def _channel() -> str:
    return os.environ.get("TONY_NOTIFY", "off").strip().lower()


def inline_keyboard(rows: list) -> dict:
    """Build a Telegram inline keyboard. rows = [[(label, callback_data), ...], ...]."""
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def notify(text: str, *, parse_mode: str = "HTML", chat_id: str | None = None,
           reply_markup: dict | None = None) -> dict:
    """Send a message on the configured channel. chat_id overrides TELEGRAM_CHAT_ID (reply to a
    specific sender). Returns {sent: bool, ...}; never raises."""
    ch = _channel()
    if ch in _OFF:
        return {"sent": False, "reason": "disabled"}
    if ch == "telegram":
        return _telegram(text, parse_mode, chat_id, reply_markup)
    return {"sent": False, "reason": f"unknown channel '{ch}'"}


def _split_message(text: str, limit: int = 4000) -> list:
    """Split a message so each piece fits Telegram's 4096-char hard limit (headroom for HTML).
    Packs whole lines; hard-splits any single oversized line. Always returns >= 1 chunk."""
    chunks: list = []
    cur = ""
    for line in (text or "").split("\n"):
        while len(line) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{cur}\n{line}" if cur else line
        if len(candidate) > limit:
            chunks.append(cur)
            cur = line
        else:
            cur = candidate
    if cur or not chunks:
        chunks.append(cur)
    return chunks


def _telegram(text: str, parse_mode: str, chat_id: str | None = None,
              reply_markup: dict | None = None) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return {"sent": False, "reason": "telegram not configured"}
    chunks = _split_message(text)
    last = len(chunks) - 1
    try:
        for i, chunk in enumerate(chunks):
            payload = {"chat_id": chat, "text": chunk, "parse_mode": parse_mode,
                       "disable_web_page_preview": True}
            if reply_markup and i == last:        # the keyboard rides only the final piece
                payload["reply_markup"] = reply_markup
            r = httpx.post(_TG_URL.format(token=token), json=payload, timeout=_TIMEOUT)
            r.raise_for_status()
        return {"sent": True}
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("notify telegram failed: %s", exc)
        return {"sent": False, "reason": str(exc)}


def broadcast(text: str, *, parse_mode: str = "HTML", reply_markup: dict | None = None) -> dict:
    """Post to the PUBLIC channel (TELEGRAM_PUBLIC_CHANNEL_ID). No-op if unset. Fail-soft."""
    if _channel() in _OFF:
        return {"sent": False, "reason": "disabled"}
    channel = os.environ.get("TELEGRAM_PUBLIC_CHANNEL_ID")
    if not channel:
        return {"sent": False, "reason": "no_public_channel"}
    return _telegram(text, parse_mode, channel, reply_markup)


def answer_callback_query(callback_id: str) -> dict:
    """Acknowledge a button tap so Telegram stops the client spinner. Fail-soft."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or not callback_id:
        return {"sent": False}
    try:
        httpx.post("https://api.telegram.org/bot{}/answerCallbackQuery".format(token),
                   json={"callback_query_id": callback_id}, timeout=_TIMEOUT)
        return {"sent": True}
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("answerCallbackQuery failed: %s", exc)
        return {"sent": False}


def edit_message_text(chat_id: str, message_id: int, text: str, *, parse_mode: str = "HTML",
                      reply_markup: dict | None = None) -> dict:
    """Edit an existing message in place (for paging). Fail-soft."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"sent": False}
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text,
               "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = httpx.post("https://api.telegram.org/bot{}/editMessageText".format(token),
                       json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        return {"sent": True}
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("editMessageText failed: %s", exc)
        return {"sent": False}


def notify_entry(symbol: str, qty, entry, stop, target, risk_pct: float = 1.0, reason: str = "") -> dict:
    """🟢 Tony placed a new entry bracket — spoken in his own voice, with the thesis.
    Posts to the operator AND the public channel (broadcast is a no-op if unconfigured)."""
    from runner.tools.tony_voice import say_entry
    msg = say_entry(symbol, qty, entry, stop, target, risk_pct, reason)
    broadcast(msg)
    return notify(msg)


def notify_exit(symbol: str, qty, exit_price, pnl, r_mult=None, reason: str = "") -> dict:
    """🟩/🟥 Tony closed a position (target/stop/his own close) — first person, with the why + R.
    Posts to the operator AND the public channel (broadcast is a no-op if unconfigured)."""
    from runner.tools.tony_voice import say_exit
    msg = say_exit(symbol, qty, exit_price, pnl, reason, r_mult)
    broadcast(msg)
    return notify(msg)


def notify_reprice(symbol: str, qty, target, stop) -> dict:
    """🔧 Tony moved a held position's protective stop/target (an intraday `adjust`)."""
    from runner.tools.tony_voice import say_reprice
    return notify(say_reprice(symbol, qty, target, stop))


def notify_daily(summary: str) -> dict:
    """📊 Once-a-day digest of Tony's book/performance. The caller leads with a first-person header
    (tony_voice.say_daily_header), so this sends the message as-is."""
    return notify(summary)
