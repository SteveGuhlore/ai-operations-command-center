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


def notify(text: str, *, parse_mode: str = "HTML") -> dict:
    """Send a message on the configured channel. Returns {sent: bool, ...}; never raises."""
    ch = _channel()
    if ch in _OFF:
        return {"sent": False, "reason": "disabled"}
    if ch == "telegram":
        return _telegram(text, parse_mode)
    return {"sent": False, "reason": f"unknown channel '{ch}'"}


def _telegram(text: str, parse_mode: str) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return {"sent": False, "reason": "telegram not configured"}
    try:
        r = httpx.post(
            _TG_URL.format(token=token),
            json={"chat_id": chat, "text": text, "parse_mode": parse_mode,
                  "disable_web_page_preview": True},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return {"sent": True}
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("notify telegram failed: %s", exc)
        return {"sent": False, "reason": str(exc)}


def _money(x) -> str:
    try:
        return f"{float(x):,.0f}"
    except (TypeError, ValueError):
        return "?"


def _px(x) -> str:
    try:
        return f"${float(x):.2f}"
    except (TypeError, ValueError):
        return "$?"


def notify_entry(symbol: str, qty, entry, stop, target, risk_pct: float = 1.0) -> dict:
    """🟢 Tony placed a new entry bracket."""
    text = (f"🟢 <b>Tony entered {symbol}</b>\n"
            f"{qty} sh @ {_px(entry)} · stop {_px(stop)} / target {_px(target)} · "
            f"{risk_pct:.0f}% risk")
    return notify(text)


def notify_exit(symbol: str, qty, exit_price, pnl, r_mult=None, reason: str = "") -> dict:
    """🟩/🟥 Tony closed a position (target/stop/his own close)."""
    try:
        pnl_f = float(pnl)
    except (TypeError, ValueError):
        pnl_f = 0.0
    emoji = "🟩" if pnl_f >= 0 else "🟥"
    sign = "+" if pnl_f >= 0 else "-"
    r = f" ({r_mult:+.1f}R)" if isinstance(r_mult, (int, float)) else ""
    why = f" · {reason}" if reason else ""
    text = (f"{emoji} <b>Tony closed {symbol}</b>\n"
            f"{qty} sh @ {_px(exit_price)} · {sign}${_money(abs(pnl_f))}{r}{why}")
    return notify(text)


def notify_reprice(symbol: str, qty, target, stop) -> dict:
    """🔧 Tony moved a held position's protective stop/target (an intraday `adjust`)."""
    text = (f"🔧 <b>Tony re-priced {symbol}</b>\n"
            f"{qty} sh · new stop {_px(stop)} / target {_px(target)}")
    return notify(text)


def notify_daily(summary: str) -> dict:
    """📊 Once-a-day digest of Tony's book/performance."""
    return notify(f"📊 <b>Tony — daily summary</b>\n{summary}")
