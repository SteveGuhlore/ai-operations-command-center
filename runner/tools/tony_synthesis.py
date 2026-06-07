"""tony_synthesis — Tony's first-person narrative reports (Phase 3, LLM).

Turns the raw book + record + self-learning into short, plain-English stories told by Tony himself:
a daily wrap, a weekly review, and a 'what I'm learning' digest. Reuses the existing model client
(agents.base.AgentBase) through one isolated _narrate seam. Everything is fail-soft and opt-in
(TONY_SYNTH=on): if the model call or any read fails, callers degrade to the plain metric digest —
a narrative is nice-to-have and must NEVER block a notification or the cycle.
"""
import logging
import os

_log = logging.getLogger(__name__)

_SYS = (
    "You ARE Tony — a friendly, honest stock trader texting a beginner friend who knows nothing about "
    "the market. Always write in FIRST PERSON ('I'). Plain, warm, concise English; if you must use a "
    "market term, add a 3-5 word plain meaning in parentheses. No hype, no financial advice, no "
    "disclaimers. Be truthful about losses. Keep it to a few short sentences a phone reads easily."
)


def synth_enabled() -> bool:
    return os.environ.get("TONY_SYNTH", "off").strip().lower() in ("on", "1", "true", "yes")


def _narrate(user_prompt: str, max_words: int = 90) -> str:
    """Single model completion as Tony. Isolated so tests mock just this. Returns '' on any failure."""
    try:
        from runner.agents.base import AgentBase
        agent = AgentBase(
            role_id="tony_synthesis",
            model=os.environ.get("TONY_SYNTH_MODEL", "gemini-2.5-flash"),
            system_prompt=_SYS,
            tools=[],
        )
        result = agent.run({"task_id": "tony-synth",
                            "body": f"{user_prompt}\n\nWrite at most {max_words} words."})
        return (result.get("output") or "").strip()
    except Exception as exc:
        _log.info("tony synthesis model call failed: %s", exc)
        return ""


# --- context builders (read-only, fail-soft) -------------------------------------------------------

def _safe(fn, default):
    try:
        return fn()
    except Exception as exc:
        _log.info("synthesis context read failed: %s", exc)
        return default


def _book_facts() -> dict:
    from runner.ledger.alpaca_paper import account_record
    from runner.ledger.tony_realized import summary as realized_summary
    acct = _safe(account_record, {"status": "err"})
    realized = _safe(realized_summary, {})
    return {"acct": acct, "realized": realized}


def daily_wrap() -> str:
    """A few-sentence first-person recap of today. '' when there's nothing to say or the model fails."""
    f = _book_facts()
    acct = f["acct"]
    if acct.get("status") != "ok":
        return ""
    pos = acct.get("open_positions", []) or []
    today = (f["realized"] or {}).get("today", {})
    unreal = sum(float(p.get("unrealized_pl", 0) or 0) for p in pos)
    facts = (
        f"Facts for today (use only these, do not invent):\n"
        f"- Account equity: {acct.get('equity')}\n"
        f"- Open positions: {len(pos)} ({', '.join(p.get('symbol', '?') for p in pos[:10]) or 'none'})\n"
        f"- Unrealized P/L on what I hold: {round(unreal, 2)}\n"
        f"- Closed today: {today.get('count', 0)} "
        f"({today.get('wins', 0)} win / {today.get('losses', 0)} loss), "
        f"realized {today.get('realized_pl', 0)}\n"
        "Tell my friend how my day went and what I'm watching, in my voice."
    )
    return _narrate(facts)


def weekly_review() -> str:
    """First-person week-in-review: results + my single biggest lesson. '' on no data / model fail."""
    from runner.ledger.tony_scorecard import compute_record
    from runner.tools.tony_outcomes import lessons_block
    rec = _safe(compute_record, {})
    if rec.get("status") != "scored" or not rec.get("graded"):
        return ""
    f = _book_facts()
    lessons = _safe(lessons_block, "") or "none yet"
    facts = (
        f"Facts (use only these):\n"
        f"- Win rate on graded calls: {rec.get('win_rate')}% over {rec.get('graded')} calls\n"
        f"- Confidence calibration (win% by my confidence): {rec.get('calibration')}\n"
        f"- All-time realized: {(f['realized'] or {}).get('all_time', {})}\n"
        f"- My own edge notes:\n{lessons}\n"
        "Give my friend a short honest week-in-review and the ONE biggest lesson I'm taking forward."
    )
    return _narrate(facts, max_words=110)


def learning_digest() -> str:
    """'What I learned studying my own trades' — surfaces the self-learning loop in human terms."""
    from runner.tools.tony_outcomes import lessons_block
    lessons = _safe(lessons_block, "")
    if not lessons:
        return ""
    facts = (
        "These are patterns I found studying my own past trades (use only these):\n"
        f"{lessons}\n"
        "Explain to my beginner friend what I learned about myself and how it changes what I'll do."
    )
    return _narrate(facts)


# --- send wrappers ---------------------------------------------------------------------------------

def send_daily_wrap() -> dict:
    txt = daily_wrap()
    if not txt:
        return {"sent": False, "reason": "no_narrative"}
    from runner.tools.notify import notify
    return notify("🗒️ <b>My day, in plain English</b>\n" + txt)


def send_weekly_review() -> dict:
    txt = weekly_review()
    if not txt:
        return {"sent": False, "reason": "no_narrative"}
    from runner.tools.notify import notify
    return notify("📅 <b>My week</b>\n" + txt)


def send_learning_digest() -> dict:
    txt = learning_digest()
    if not txt:
        return {"sent": False, "reason": "no_narrative"}
    from runner.tools.notify import notify
    return notify("🧠 <b>What I'm learning about myself</b>\n" + txt)
