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
     "Call `queue_research_candidate` ONCE PER NAME (symbol, score, confidence, proposed_target, "
     "proposed_stop, thesis_ref, source) — do NOT hand-write workspace/research-queue.json; the tool "
     "persists, dedupes, and ranks each row for you. Only queue names with a real proposed_target AND "
     "proposed_stop — the queue is re-validated against fresh prices at the next open and survivors "
     "auto-execute. Narrating that you 'wrote the queue' without calling the tool means nothing was "
     "saved (the #1 failure of this step)."),
]

# Follow-on research ROUNDS staged AFTER the main wave (round 0) drains — one round per drain, in
# order, then the repeating _DISCOVERY_CYCLE below. Genuinely-new, deeper work led by a self-learning
# battery that exploits Tony's
# already-built analytics (tony_scorecard.discover_edges / calibration / sizing_attribution) and his
# real realized record. Each entry: (title, task_type, body).
_ROUNDS = [
    # Round 1 — Self-Learning Battery (the lead). Cheap, compounding, mostly reuses on-disk data.
    [
        ("Tony Calibration Study", "tony_calibration_study",
         "Study your OWN confidence calibration. Read the `calibration` block in "
         "vault/tony-stocks/tony_stocks_record.json (win-rate per confidence bucket). Does "
         "`confidence: high` actually beat `medium` and `low`? If high under-performs low, your "
         "confidence is miscalibrated — say so. Cross-check a few high- vs low-confidence verdicts "
         "against their outcomes to find WHY. Write the finding with `write_tony_insight` and add one "
         "concrete, evidence-tagged calibration rule to "
         "vault/agents/market_research_worker/learned_rules.md."),
        ("Tony Edge Mining", "tony_edge_mining",
         "Mine your graded history for repeatable edges. The scorecard's `discover_edges` tallies "
         "evidence-tag → win-rate; review your strongest AND weakest tags (e.g. which setups/"
         "fundamentals you actually win or lose on). Sanity-check the top and bottom tags against the "
         "underlying picks so you don't over-fit a small sample. Codify the durable ones into "
         "vault/tony-stocks/pattern-library.md with the tag, sample size, and win-rate."),
        ("Tony Realized Post-Mortem", "tony_realized_postmortem",
         "Post-mortem every LOSS in workspace/tony-realized.json (your real stop-outs, not verdict-vs-"
         "scanner). For each loser, pull `get_stock_news` / `get_price_history` around the exit and tag "
         "the failure mode (gap-down, broke support, earnings miss, thesis never triggered, stop too "
         "tight). Aggregate the recurring failure modes and write the top 1-3 as `write_tony_insight` "
         "lessons + a guardrail in vault/agents/market_research_worker/learned_rules.md."),
        ("Tony Re-Grade", "tony_regrade",
         "Re-grade picks whose outcomes have now RESOLVED since your last review. Compare your verdict "
         "to what actually happened; where a thesis aged badly, note WHY (what you missed) and update "
         "the relevant vault/tickers/<SYM>.md and pattern-library.md. End with one `write_tony_insight` "
         "naming the single adjustment that would have flipped the most losers."),
    ],
    # Round 2 — Deepen top-conviction names (second-pass, multi-angle) on the ranked queue.
    [
        ("Tony Conviction Deep-Dive", "tony_conviction_deepdive",
         "Take the top 5 names from workspace/research-queue.json and run a SECOND, deeper pass on "
         "each: (a) a thesis pre-mortem ('it's 3 weeks later and this lost — why?'), (b) a stress-test "
         "against fresh `get_stock_news` + `web_research`, and (c) a quick competitor / supply-chain "
         "read. For any name whose thesis weakens, write a revised `write_tony_verdict` (tighter stop "
         "or step-off) so the open re-check sees your updated call. Record the deeper reads in "
         "vault/tickers/<SYM>.md."),
    ],
    # Round 3 — Broaden beyond the scanner: cross-asset / macro / sector + fresh idea hunt.
    [
        ("Tony Broaden Scan", "tony_broaden_scan",
         "Broaden beyond the scanner universe. Use `regime` + `web_research` for a cross-asset / "
         "sector-rotation read (which groups are leading/lagging into the open), then hunt 3-5 fresh "
         "high-quality setups OUTSIDE the current watchlist that fit the regime. Record each with the "
         "`tony_ideas` tool (thesis, proposed target/stop, confidence) so they feed the next ranked "
         "queue."),
    ],
]

# After _ROUNDS drains, KEEP working the rest of the closed window instead of idling ~22h: cycle
# these two passes (one round per drain, alternating) so each pass does genuinely-NEW work rather
# than re-reading the static records _ROUNDS already covered. Discovery originates names the bot
# is NOT scanning; second-opinion re-examines the bot's OWN scanned list for entries it skipped.
# Both feed the ranked queue (and tony_ideas), which also keeps research-queue.json populated.
_DISCOVERY_CYCLE = [
    [
        ("Tony Discovery Scan", "tony_discovery_scan",
         "Originate FRESH candidates the bot is NOT scanning. Read `regime` for the current "
         "sector-rotation read, then use `web_research` to surface 3-5 high-quality setups OUTSIDE "
         "the ALREADY COVERED list below that fit the regime (sector themes, post-earnings drift, "
         "fresh catalysts). VALIDATE each with `get_stock_data` + `get_price_history` — use REAL "
         "levels, never invent them. Log each with `log_tony_idea` (thesis, source, score), and for "
         "any name with a real proposed_target AND proposed_stop also call `queue_research_candidate` "
         "so the next open re-check can act on it. Skip anything already on the list."),
    ],
    [
        ("Tony Second-Opinion Sweep", "tony_second_opinion",
         "Second-opinion pass on the BOT's own scanned universe (the names listed below) for entries "
         "the bot did NOT flag. Pick names you have not already deep-dived this window, pull "
         "`get_stock_data` + `get_price_history` + `get_stock_news`, and where YOU see a real setup "
         "the bot skipped, write a `write_tony_verdict` (with target & stop) or `log_tony_idea` so it "
         "feeds the ranked queue. Don't force calls — only flag genuine setups with real levels."),
    ],
]

# Per-open ceiling on follow-on rounds (the 3 _ROUNDS + the repeating _DISCOVERY_CYCLE). The
# off-hours budget lane is the real nightly spend cap; this just stops a fast-draining pass from
# looping unbounded if budget is generous.
_MAX_FOLLOWUP_ROUNDS = 12


def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def _write_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Atomic: a crash mid-write would corrupt the state into invalid JSON, which _read_state
    # degrades to {} — losing staged_for and re-staging the whole wave (dozens of dup tasks).
    tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


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


_REALIZED_TASKS = {"tony_self_review", "tony_realized_postmortem", "tony_regrade"}
_SMALL_SAMPLE_TASKS = {"tony_calibration_study", "tony_edge_mining"}
_DISCOVERY_TASKS = {"tony_discovery_scan"}
_SECOND_OPINION_TASKS = {"tony_second_opinion"}


def _recent_idea_symbols(limit: int = 40) -> list:
    """Symbols Tony has already originated (tony_stocks_ideas.json), newest first — part of the
    discovery exclude set so each pass hunts new ground instead of resurfacing the same names."""
    try:
        from runner.tools.tony_ideas import IDEAS_FILE
        entries = json.loads(IDEAS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError, ImportError):
        return []
    out = []
    for e in reversed(entries if isinstance(entries, list) else []):
        s = (e.get("symbol") or "").upper()
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def _discovery_exclude_block() -> str:
    """For the discovery pass: the 'already covered' set (bot's scanned universe + Tony's recent
    ideas) to hunt OUTSIDE. Deterministic; fail-soft to empty (the body still stands alone)."""
    covered = []
    for s in _universe_symbols() + _recent_idea_symbols():
        if s and s not in covered:
            covered.append(s)
    if not covered:
        return ""
    return ("\n\n--- ALREADY COVERED — hunt OUTSIDE these ---\n"
            "The bot already scans these and you've already logged ideas on some. Do NOT re-pitch "
            "any of them; find genuinely NEW names:\n" + ", ".join(covered))


def _second_opinion_universe_block() -> str:
    """For the second-opinion pass: the bot's scanned universe is the TARGET to re-examine, with
    names you've already originated flagged to skip. Deterministic; fail-soft to empty."""
    universe = _universe_symbols()
    if not universe:
        return ""
    block = "\n\n--- THE BOT'S SCANNED UNIVERSE (re-examine THESE) ---\n" + ", ".join(universe)
    already = _recent_idea_symbols()
    if already:
        block += "\n\nAlready originated (skip — don't re-log): " + ", ".join(already)
    return block


def _realized_block() -> str:
    """Render Tony's REAL closed-trade record (Alpaca-reconciled) as ground truth for the learning
    tasks, so the agent doesn't fall back to the thin 1-sample verdict track. Fail-soft -> guidance."""
    try:
        from runner.ledger.tony_realized import records, summary
        rows = records(newest_first=True)
        s = (summary() or {}).get("all_time", {})
    except Exception:
        return ""
    if not s.get("count"):
        return ("\n\n--- YOUR REAL REALIZED RECORD (ground truth) ---\n"
                "No closed trades on record yet. Do NOT infer performance from the verdict-vs-scanner "
                "track (`tony_outcomes` / `tony_stocks_record.json`) — it is a thin side-metric, not "
                "your P/L. With no realized data, say so plainly and write NO performance lesson.")
    lines = [f"- {r.get('symbol')}: {r.get('realized_pl')} ({r.get('pct')}%) on {r.get('date')}, "
             f"reason={r.get('reason')}" for r in rows[:25]]
    return (
        "\n\n--- YOUR REAL REALIZED RECORD (ground truth — use THIS, not the verdict track) ---\n"
        f"All-time: {s.get('count')} closed, {s.get('wins')} win / {s.get('losses')} loss, "
        f"realized P/L {s.get('realized_pl')}. By reason: {s.get('by_reason')}.\n"
        + "\n".join(lines) +
        "\n(The `tony_outcomes` / `tony_stocks_record.json` verdict track is a thin side-metric — do "
        "NOT draw performance conclusions from it. THIS realized ledger is the truth.)")


def _small_sample_guard() -> str:
    return ("\n\nGUARD: if you have fewer than 5 graded verdicts, state 'insufficient data' and write "
            "NO positive performance lesson — a single outcome is noise, not signal.")


def _augment_body(task_type: str, body: str) -> str:
    """Hand the learning tasks the real realized record (or a small-sample guard) so they stop
    manufacturing rosy lessons from the 1-sample verdict track. Pure given the ledger read."""
    if task_type in _REALIZED_TASKS:
        return body + _realized_block()
    if task_type in _SMALL_SAMPLE_TASKS:
        return body + _small_sample_guard()
    if task_type in _DISCOVERY_TASKS:
        return body + _discovery_exclude_block()
    if task_type in _SECOND_OPINION_TASKS:
        return body + _second_opinion_universe_block()
    return body


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
                    task_type, _augment_body(task_type, body), priority)
        enqueued += 1

    state["staged_for"] = open_date
    state["staged_at"] = (now or datetime.now(_ET)).isoformat()
    state["task_count"] = enqueued
    _write_state(state)
    _log.info("research_wave: staged %d tasks for the %s open", enqueued, open_date)
    return {"staged": True, "open_date": open_date, "task_count": enqueued}


def _rw_tasks_outstanding() -> bool:
    """True while any TONY-RW-* task (main wave or a follow-on round) is still in todo/ or
    in_progress/. The follow-up gate waits for this to clear so rounds are paced by COMPLETION,
    not a timer (mirrors main._pitch_is_alive's two-folder check)."""
    in_progress = TASKS_DIR.parent / "in_progress"
    for folder in (TASKS_DIR, in_progress):
        if folder.exists() and any(folder.glob("TONY-RW-*.md")):
            return True
    return False


def maybe_stage_research_followups(now: datetime | None = None) -> dict:
    """After the main wave drains, stage the next research round, one round per drain. First the 3
    fixed _ROUNDS (self-learning → deepen → broaden), then the repeating _DISCOVERY_CYCLE (discover
    new names ↔ second-opinion the bot's list) until `_MAX_FOLLOWUP_ROUNDS`, so the closed window
    keeps doing NEW work instead of idling. No-op when the market is open, the main wave for the
    upcoming open isn't staged yet, the prior round is still draining, or the ceiling is reached."""
    if market_session(now) != "closed":
        return {"staged": False, "reason": "market_open"}

    open_date = _next_open_date(now)
    state = _read_state()
    if state.get("staged_for") != open_date:
        return {"staged": False, "reason": "wave_not_staged", "open_date": open_date}

    rounds_done = state.get("rounds_done") or {}
    done = int(rounds_done.get(open_date, 0))
    if _rw_tasks_outstanding():
        return {"staged": False, "reason": "prior_round_draining", "open_date": open_date}
    if done >= _MAX_FOLLOWUP_ROUNDS:
        return {"staged": False, "reason": "exhausted", "open_date": open_date}

    # First the fixed learning rounds, then cycle the discovery passes (alternating).
    round_tasks = (_ROUNDS[done] if done < len(_ROUNDS)
                   else _DISCOVERY_CYCLE[(done - len(_ROUNDS)) % len(_DISCOVERY_CYCLE)])
    round_no = done + 1
    suffix = open_date.replace("-", "")
    enqueued = 0
    for title, task_type, body in round_tasks:
        _write_task(f"TONY-RW-R{round_no}-{task_type.upper()}-{suffix}",
                    f"{title} (for {open_date} open)", task_type, _augment_body(task_type, body))
        enqueued += 1

    rounds_done[open_date] = round_no
    state["rounds_done"] = rounds_done
    state["followup_staged_at"] = (now or datetime.now(_ET)).isoformat()
    _write_state(state)
    _log.info("research_wave: staged follow-up round %d (%d tasks) for the %s open",
              round_no, enqueued, open_date)
    return {"staged": True, "round": round_no, "open_date": open_date, "task_count": enqueued}
