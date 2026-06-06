"""research_wave — off-market research orchestrator (Component B).

When the market is CLOSED and no wave is yet staged for the upcoming open, enqueue ONE structured
wave of research tasks so Tony prepares for the next open instead of sitting idle: deep-dive the
full scanner universe, synthesize macro, scan catalysts, hunt fresh ideas, stress-test the book,
self-review against his real realized record, and finally rank everything into research-queue.json.

Every task is a TASK TYPE under the single agent (assigned_agent: market_research_worker,
pod: stock_research_pod) — no new runtime agent personas. De-dup is keyed by the target open date
in workspace/research-wave-state.json so re-entering the closed window never double-enqueues.
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from runner.ledger.market_clock import _ET, _HOLIDAYS_2026, market_session

_log = logging.getLogger(__name__)

TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks" / "todo"
STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "research-wave-state.json"
BRIDGE_MD_DIR = Path(os.environ.get(
    "TONY_BRIDGE_DIR",
    str(Path(__file__).parent.parent.parent / "bridge" / "tony-stocks"),
))
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

# The six fixed wave tasks (besides the per-symbol deep-dives). tony_research_rank is last and
# depends on the wave's output. (title, task_type, body)
_WAVE_TASKS = [
    ("Tony Macro Synthesis", "tony_macro_synthesis",
     "Read the `regime` tool output and `vault/macro/sector-rotation.md`. Write a concise macro/"
     "regime read for the upcoming open: which sectors are favored, what risk is on/off, and how "
     "it should bias entries. Record 1-3 `write_tony_insight` notes."),
    ("Tony Catalyst Scan", "tony_catalyst_scan",
     "Scan the upcoming earnings calendar and fresh news/SEC catalysts across the scanner universe "
     "and watchlist using `get_catalysts` and `get_stock_news`. Flag any name with an event inside "
     "the trade window (earnings, 8-K, insider activity). Note catalysts that change conviction."),
    ("Tony Idea Hunt", "tony_idea_hunt",
     "Hunt for high-quality setups BEYOND the scanner universe. Use `web_research` + `get_stock_data` "
     "to surface fresh candidates, then record each promising name with the `tony_ideas` tool "
     "(thesis, proposed target/stop, confidence)."),
    ("Tony Book Stress-Test", "tony_book_stresstest",
     "Re-examine EVERY open position against fresh overnight news. For each: pull `get_stock_data` + "
     "`get_stock_news`, decide if the thesis still holds. If broken, write a `close` verdict (or an "
     "`adjust` to tighten the stop) so the open re-check can act on it."),
    ("Tony Self-Review", "tony_self_review",
     "Grade your OWN realized record (workspace/tony-realized.json — your real stop-outs and wins, "
     "not just verdict-vs-scanner). Where were you right/wrong and WHY? Write `write_tony_insight` "
     "lessons and update vault/agents/market_research_worker/learned_rules.md and "
     "vault/tony-stocks/pattern-library.md with concrete, evidence-tagged adjustments."),
    ("Tony Research Rank", "tony_research_rank",
     "FINAL step — synthesize this window's verdicts + ideas into a scored, ranked candidate queue. "
     "Write workspace/research-queue.json: a best-first list of "
     "{symbol, thesis_ref, score, confidence, proposed_target, proposed_stop, source, generated_at} "
     "with a generated_at + target-open-date header. This queue is re-validated at the next open "
     "before anything executes."),
]


def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def _write_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _next_open_date(now: datetime | None = None) -> str:
    """The next date the market opens (skips weekends + known holidays) from `now` (ET).
    During a closed weeknight this is the next weekday; over a weekend/holiday it rolls forward."""
    if now is None:
        now = datetime.now(_ET)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    now = now.astimezone(_ET)
    # If it's a weekday before the close, the next open is today; otherwise advance.
    d = now.date()
    if not (now.weekday() < 5 and now.hour < 16 and d.strftime("%Y-%m-%d") not in _HOLIDAYS_2026):
        d = d + timedelta(days=1)
    while d.weekday() >= 5 or d.strftime("%Y-%m-%d") in _HOLIDAYS_2026:
        d = d + timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def _latest_bridge_md() -> str:
    if not BRIDGE_MD_DIR.exists():
        return ""
    files = sorted([f for f in BRIDGE_MD_DIR.glob("*.md") if _DATE_RE.match(f.stem)])
    if not files:
        return ""
    try:
        return files[-1].read_text(encoding="utf-8")
    except OSError:
        return ""


def _universe_symbols() -> list:
    """Full scanner universe (Tier 1+2+3) from the newest bridge — the breadth the wave covers."""
    md = _latest_bridge_md()
    if not md:
        return []
    from runner.bridge.tony_bridge import _parse_bridge_signals
    sig = _parse_bridge_signals(md)
    out = []
    for s in sig.get("tier1", []) + sig.get("newer", []):
        sym = s.get("symbol")
        if sym and sym not in out:
            out.append(sym)
    return out


def _write_task(task_id: str, title: str, task_type: str, body: str, priority: str = "normal") -> None:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    (TASKS_DIR / f"{task_id}.md").write_text(
        f"---\n"
        f"task_id: {task_id}\n"
        f"assigned_agent: market_research_worker\n"
        f"status: todo\n"
        f"priority: {priority}\n"
        f"pod: stock_research_pod\n"
        f"task_type: {task_type}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )


def maybe_stage_research_wave(now: datetime | None = None) -> dict:
    """Stage exactly one off-market research wave for the upcoming open. No-op when the market is
    open or a wave is already staged for that open date."""
    if market_session(now) != "closed":
        return {"staged": False, "reason": "market_open"}

    open_date = _next_open_date(now)
    state = _read_state()
    if state.get("staged_for") == open_date:
        return {"staged": False, "reason": "already_staged", "open_date": open_date}

    suffix = open_date.replace("-", "")
    enqueued = 0
    for sym in _universe_symbols():
        _write_task(
            f"TONY-RW-TKR-{sym}-{suffix}",
            f"Off-market deep-dive — {sym} (for {open_date} open)",
            "ticker_deepdive",
            f"Off-hours deep-dive verdict for **{sym}** ahead of the {open_date} open. Steps:\n"
            f"1. `get_stock_data('{sym}')` — fundamentals + next earnings date.\n"
            f"2. `get_price_history('{sym}')` — your own RSI/SMA/ATR/volume read.\n"
            f"3. `get_stock_news('{sym}')` + `web_research` — news/catalysts.\n"
            f"4. `write_tony_verdict(...)` — independent score + verdict + (for adjust/override) "
            f"your target & stop. Note: closed-market entries do NOT execute now; this feeds the "
            f"ranked queue that the next open re-validates against fresh prices.\n"
            f"Then append findings to `vault/tickers/{sym}.md`.",
        )
        enqueued += 1

    for title, task_type, body in _WAVE_TASKS:
        priority = "high" if task_type == "tony_research_rank" else "normal"
        _write_task(f"TONY-RW-{task_type.upper()}-{suffix}", f"{title} (for {open_date} open)",
                    task_type, body, priority)
        enqueued += 1

    state["staged_for"] = open_date
    state["staged_at"] = (now or datetime.now(_ET)).isoformat()
    state["task_count"] = enqueued
    _write_state(state)
    _log.info("research_wave: staged %d tasks for the %s open", enqueued, open_date)
    return {"staged": True, "open_date": open_date, "task_count": enqueued}
