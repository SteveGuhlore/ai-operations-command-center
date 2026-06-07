"""tony_voice — Tony's first-person voice for Telegram (pure formatting, no I/O).

Tony is his own person: every line is "I", as Tony, in plain English a non-trader can follow, with
the real numbers underneath and a light teach-as-you-go tone so the reader slowly learns the *why*.
These are pure string builders so they unit-test cleanly; notify.py wraps them with the HTTP send.
Output is Telegram HTML (parse_mode=HTML), so only <b>/<i> are used.
"""
from __future__ import annotations


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


def say_entry(symbol, qty, entry, stop, target, risk_pct: float = 1.0, reason: str = "") -> str:
    """🟢 A new position, explained: where I think it goes, and how I cap the downside."""
    head = (f"🟢 <b>I bought {symbol}.</b> I think it climbs from {_px(entry)} toward {_px(target)}. "
            f"If it drops to {_px(stop)} I'll sell automatically, so a wrong call only costs about "
            f"{risk_pct:.0f}% of the account.")
    nums = f"{qty} sh · entry {_px(entry)} · stop {_px(stop)} · target {_px(target)}"
    why = f"\n<i>Why: {reason.strip()}</i>" if reason and reason.strip() else ""
    return f"{head}\n{nums}{why}"


def say_exit(symbol, qty, exit_price, pnl, reason: str = "", r_mult=None) -> str:
    """🟩/🟥 A close, explained: did I win or lose, and WHY did it end (target / stop / my call)."""
    try:
        pnl_f = float(pnl)
    except (TypeError, ValueError):
        pnl_f = 0.0
    win = pnl_f >= 0
    emoji = "🟩" if win else "🟥"
    amount = f"+${_money(pnl_f)} win" if win else f"${_money(abs(pnl_f))} loss"

    if reason == "target":
        because = "It hit my price target"
        if isinstance(r_mult, (int, float)):
            because += f" — that's {abs(r_mult):.1f}× what I risked"
        because += "."
    elif reason == "stop":
        because = "It hit my safety stop, so I cut it before it got worse."
    elif reason == "close":
        because = "I decided the setup had played out and stepped aside."
    else:
        because = "The position closed out."

    head = f"{emoji} <b>I sold {symbol} for a {amount}.</b> {because}"
    nums = f"{qty} sh · exit {_px(exit_price)}"
    return f"{head}\n{nums}"


def say_reprice(symbol, qty, target, stop) -> str:
    """🔧 Moved the protective levels, explained as managing the position."""
    head = (f"🔧 <b>I adjusted {symbol}.</b> I moved my safety stop to {_px(stop)} and target to "
            f"{_px(target)} — managing the trade as it moves.")
    nums = f"{qty} sh · stop {_px(stop)} · target {_px(target)}"
    return f"{head}\n{nums}"


def say_daily_header(equity, day_delta=None) -> str:
    """First-person lead for the daily digest; the metric lines follow underneath."""
    if day_delta is None:
        return "📊 <b>Here's where I stand today.</b>"
    try:
        d = float(day_delta)
    except (TypeError, ValueError):
        return "📊 <b>Here's where I stand today.</b>"
    if d > 0:
        mood = f"Good day — I'm up ${_money(d)} on the account."
    elif d < 0:
        mood = f"Down day — I gave back ${_money(abs(d))}, part of the game."
    else:
        mood = "Quiet day — about flat on the account."
    return f"📊 <b>Here's my day.</b> {mood}"
