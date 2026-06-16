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


def say_entry(
    symbol, qty, entry, stop, target, risk_pct: float = 1.0, reason: str = ""
) -> str:
    """🟢 A new position, explained: where I think it goes, and how I cap the downside."""
    head = (
        f"🟢 <b>I bought {symbol}.</b> I think it climbs from {_px(entry)} toward {_px(target)}. "
        f"If it drops to {_px(stop)} I'll sell automatically, so a wrong call only costs about "
        f"{risk_pct:.0f}% of the account."
    )
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
    head = (
        f"🔧 <b>I adjusted {symbol}.</b> I moved my safety stop to {_px(stop)} and target to "
        f"{_px(target)} — managing the trade as it moves."
    )
    nums = f"{qty} sh · stop {_px(stop)} · target {_px(target)}"
    return f"{head}\n{nums}"


def say_reprice_lock(symbol, qty, stop, entry=None) -> str:
    """🔒 The first time a stop crosses into profit — the position can no longer lose money."""
    where = f" (my entry was {_px(entry)})" if entry is not None else ""
    head = (
        f"🔒 <b>{symbol} is now risk-free.</b> I raised my safety stop to {_px(stop)}{where}, at "
        f"or above where I bought — so this trade can't turn into a loss now."
    )
    nums = f"{qty} sh · stop {_px(stop)}"
    return f"{head}\n{nums}"


def say_status(acct: dict, realized: dict | None = None) -> str:
    """First-person 'how am I doing right now' for the /status chat command (pure)."""
    pos = (acct or {}).get("open_positions", []) or []
    equity = (acct or {}).get("equity")
    lines = ["📍 <b>Here's where I stand right now.</b>"]
    if isinstance(equity, (int, float)):
        lines.append(f"My account is at ${_money(equity)}.")
    if pos:
        unreal = sum(float(p.get("unrealized_pl", 0) or 0) for p in pos)
        names = ", ".join(p.get("symbol", "?") for p in pos[:8])
        ud = "up" if unreal >= 0 else "down"
        lines.append(
            f"I'm holding {len(pos)} stock(s): {names}. "
            f"Together they're {ud} ${_money(abs(unreal))} so far."
        )
    else:
        lines.append(
            "I'm not holding anything at the moment — I'd rather wait than force a bad trade."
        )
    t = (realized or {}).get("today", {}) if realized else {}
    if t.get("count"):
        lines.append(
            f"Today I closed {t['count']} ({t.get('wins', 0)} win / {t.get('losses', 0)} "
            f"loss) for ${_money(t.get('realized_pl', 0))} realized."
        )
    return "\n".join(lines)


def say_record(
    rec: dict, edges: dict | None = None, realized: dict | None = None
) -> str:
    """First-person track record for /record (pure). Leads with my REAL closed trades (actual wins,
    losses, $ — from the Alpaca-reconciled ledger), then scanner-pick accuracy + my edges."""
    r = (realized or {}).get("all_time", {}) if realized else {}
    lines = ["📈 <b>My track record so far.</b>"]
    if r.get("count"):
        wins, losses, pl = (
            r.get("wins", 0),
            r.get("losses", 0),
            float(r.get("realized_pl", 0) or 0),
        )
        verb = "made" if pl >= 0 else "lost"
        lines.append(
            f"I've closed {r['count']} trades — {wins} winner(s), {losses} loser(s) — and "
            f"{verb} ${_money(abs(pl))} overall."
        )
        stops = (r.get("by_reason") or {}).get("stop", 0)
        if stops:
            lines.append(
                f"{stops} of those were me cutting a loss at my stop — that's discipline, "
                "not failure; it's how I keep a bad trade small."
            )
    else:
        lines.append("I haven't closed any trades yet — still early.")

    if rec and rec.get("status") == "scored" and rec.get("graded"):
        lines.append(
            f"On the scanner's picks, I've called it right about {rec.get('win_rate')}% "
            f"of {rec.get('graded')} times."
        )
    cal = (rec or {}).get("calibration") or {}
    hi, lo = cal.get("high"), cal.get("low")
    if isinstance(hi, (int, float)) and isinstance(lo, (int, float)):
        if hi >= lo:
            lines.append(
                f"When I say I'm confident, I'm right more often ({hi}% vs {lo}%) — "
                "so my gut is calibrated."
            )
        else:
            lines.append(
                f"Honest note: lately my 'confident' calls ({hi}%) haven't beaten my "
                f"cautious ones ({lo}%) — I'm recalibrating."
            )
    if edges and edges.get("edges"):
        ranked = edges["edges"]
        winners = [e for e in ranked if e["win_rate"] >= 55][:2]
        losers = [e for e in ranked if e["win_rate"] <= 45][-2:]
        if winners:
            lines.append("I do best on: " + ", ".join(e["tag"] for e in winners) + ".")
        if losers:
            lines.append(
                "I struggle with: "
                + ", ".join(e["tag"] for e in losers)
                + " — I'm working on those."
            )
    return "\n".join(lines)


_REASON_WORD = {
    "stop": "hit my stop",
    "target": "hit my target",
    "close": "I stepped aside",
    "unknown": "closed out",
}


def _day_label(date_str) -> str:
    """Friendly short day for a YYYY-MM-DD: weekday for the last week, else MM-DD."""
    from datetime import date, datetime

    try:
        d = datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return str(date_str or "")
    from runner.ledger.market_clock import trading_day

    delta = (datetime.strptime(trading_day(), "%Y-%m-%d").date() - d).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if 0 < delta < 7:
        return d.strftime("%a")
    return d.strftime("%m-%d")


def _record_row(r: dict) -> str:
    pl = float(r.get("realized_pl", 0) or 0)
    emoji = "🟩" if pl >= 0 else "🟥"
    amt = f"+${_money(pl)}" if pl >= 0 else f"−${_money(abs(pl))}"
    pct = r.get("pct")
    pct_s = f" ({pct:+.1f}%)" if isinstance(pct, (int, float)) else ""
    why = _REASON_WORD.get(r.get("reason", "unknown"), "closed out")
    return f"{emoji} <b>{r.get('symbol', '?')}</b> {amt}{pct_s} · {_day_label(r.get('date'))} · {why}"


def _record_summary(realized: dict | None) -> str:
    r = (realized or {}).get("all_time", {}) if realized else {}
    if not r.get("count"):
        return "I haven't closed any trades yet — still early."
    wins, losses, pl = (
        r.get("wins", 0),
        r.get("losses", 0),
        float(r.get("realized_pl", 0) or 0),
    )
    verb = "made" if pl >= 0 else "lost"
    return (
        f"I've closed {r['count']} trades — {wins} winner(s), {losses} loser(s) — and "
        f"{verb} ${_money(abs(pl))} overall."
    )


def say_record_page(
    rows: list, realized: dict | None, page: int = 0, page_size: int = 12
) -> dict:
    """Paged track record: {'text', 'has_more', 'page'}. Page 0 leads with the summary; every page
    lists up to page_size closed trades (newest first). Pure."""
    page = max(0, int(page))
    start = page * page_size
    chunk = rows[start : start + page_size]
    lines = []
    if page == 0:
        lines.append("📈 <b>My track record so far.</b>")
        lines.append(_record_summary(realized))
    else:
        lines.append(f"📈 <b>More closed trades</b> (page {page + 1})")
    lines.extend(_record_row(r) for r in chunk)
    if not chunk:
        lines.append("That's all of them.")
    return {
        "text": "\n".join(lines),
        "has_more": start + page_size < len(rows),
        "page": page,
    }


def say_explain(symbol: str, thesis: str, held: bool) -> str:
    """First-person 'why this stock' for /explain SYM (pure)."""
    if not symbol:
        return "Tell me which stock and I'll explain my thinking — like <code>/explain NVDA</code>."
    sym = symbol.upper()
    base = (
        f"<b>{sym}:</b> {thesis}"
        if thesis
        else f"I don't have a recent write-up on {sym} yet."
    )
    hold = (
        " I'm holding it right now." if held else " I'm not holding it at the moment."
    )
    return base + hold


HELP = (
    "👋 <b>Hey, I'm Tony.</b> I trade a paper account and I'll explain everything in plain English.\n"
    "Text me:\n"
    "• <code>/status</code> — how I'm doing right now\n"
    "• <code>/record</code> — my track record, honestly\n"
    "• <code>/explain NVDA</code> — why I'm in (or out of) a stock\n"
    "• <code>/glossary</code> — plain-English meanings of words I use\n"
    "• <code>/help</code> — this menu"
)

GLOSSARY = (
    "📖 <b>Plain-English glossary</b>\n"
    "• <b>Entry</b> — the price I bought at.\n"
    "• <b>Stop</b> — my pre-set 'I was wrong' exit; it caps the loss automatically.\n"
    "• <b>Target</b> — the price I'm aiming to sell at for a profit.\n"
    "• <b>R / R-multiple</b> — how many times my risk I made. +2R = I made twice what I'd risked.\n"
    "• <b>Risk %</b> — how much of the whole account I'd lose if a trade hits its stop (I keep it ~1%).\n"
    "• <b>Unrealized P/L</b> — paper profit on stocks I still hold (not banked yet).\n"
    "• <b>Realized P/L</b> — actual profit/loss on trades I've already closed."
)


def say_day_ledger(rows_today: list, today_agg: dict | None = None) -> str:
    """Deterministic end-of-day trade ledger: EVERY exit closed today as its own line, plus the
    win/loss tally. Rides under the LLM wrap prose so the day report always shows what was
    actually sold — the narrative model may summarize, but the ledger never omits. Pure; ''
    when nothing closed."""
    if not rows_today:
        return ""
    lines = ["", "<b>Today's closed trades:</b>"]
    lines.extend(_record_row(r) for r in rows_today)
    t = today_agg or {}
    if t.get("count"):
        pl = float(t.get("realized_pl", 0) or 0)
        amt = f"+${_money(pl)}" if pl >= 0 else f"−${_money(abs(pl))}"
        lines.append(
            f"Net: <b>{amt}</b> realized · {t.get('wins', 0)} win / {t.get('losses', 0)} loss"
        )
    return "\n".join(lines)


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
