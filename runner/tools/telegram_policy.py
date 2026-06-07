"""telegram_policy — public-tier guardrails for Tony's Telegram face.

Tony answers the operator (TELEGRAM_CHAT_ID) with everything, and the public with a read-only,
rate-limited, watchlist-free subset. Pure tier/allowlist logic + a small persisted rate-limit and a
canned-FAQ matcher so common questions never touch the LLM. Fail-soft: a bad state file degrades to
"allow nothing extra", never an exception into the cycle.
"""
import json
import logging
import os
import time
from pathlib import Path

_log = logging.getLogger(__name__)
STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "telegram-public-state.json"

# Commands the PUBLIC tier may run. Watchlist / "what he's eyeing next" is operator-only
# (front-running guard); everything that reports the realized past is public.
_PUBLIC_COMMANDS = {"start", "help", "status", "book", "record", "stats",
                    "explain", "why", "glossary", "terms"}

_FAQ = [
    (("real money", "real cash", "actual money", "really trading"),
     "It's a <b>paper account</b> — real prices, simulated money. So the trades and P/L are real "
     "decisions, but no actual cash is at stake. That's how I learn out loud without risking anyone."),
    (("what do you trade", "which stocks", "what stocks"),
     "US stocks — liquid names with clean setups. I post every entry and exit here with the why."),
    (("who are you", "what are you", "are you a bot", "are you ai"),
     "I'm Tony — an AI trader running a paper account. I think out loud and explain everything in "
     "plain English so you can follow along and learn."),
    (("advice", "should i buy", "should i sell", "tip"),
     "I can't give financial advice — I only narrate my own paper trades and reasoning. Always do "
     "your own homework before risking real money."),
]


def is_operator(chat_id) -> bool:
    return str(chat_id) == str(os.environ.get("TELEGRAM_CHAT_ID", ""))


def tier_for(chat_id) -> str:
    return "operator" if is_operator(chat_id) else "public"


def command_allowed(cmd: str, tier: str) -> bool:
    if tier == "operator":
        return True
    return (cmd or "").lower() in _PUBLIC_COMMANDS


def faq_answer(text: str):
    t = (text or "").lower()
    for keys, answer in _FAQ:
        if any(k in t for k in keys):
            return answer
    return None


def _load_state() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError as exc:
        _log.info("public state write failed: %s", exc)


def allow_nl(user_id, now: float | None = None) -> bool:
    """Consume one public NL allowance. False (no model call) when the per-user hourly window or the
    global daily cap is exceeded. Records the grant on success. Fail-soft."""
    now = time.time() if now is None else now
    per_user = int(os.environ.get("TONY_PUBLIC_NL_PER_USER_HOUR", "5"))
    daily_cap = int(os.environ.get("TONY_PUBLIC_NL_DAILY_CAP", "100"))
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    st = _load_state()
    if st.get("day") != day:
        st = {"day": day, "global": 0, "users": {}}
    users = st.setdefault("users", {})
    hits = [t for t in users.get(str(user_id), []) if now - t < 3600]
    if len(hits) >= per_user:
        users[str(user_id)] = hits
        _save_state(st)
        return False
    if int(st.get("global", 0)) >= daily_cap:
        return False
    hits.append(now)
    users[str(user_id)] = hits
    st["global"] = int(st.get("global", 0)) + 1
    _save_state(st)
    return True
