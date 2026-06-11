import json
import logging
import os
import re
import time
from pathlib import Path

from runner.tools.tony_outcomes import track_record_block, lessons_block
from runner.tools.tony_book import book_block, execution_feedback_block
from runner.tools.market_regime import regime_header

_log = logging.getLogger(__name__)


def _safe_block(fn) -> str:
    """Render a brief enrichment block, swallowing any failure so a bad cache / missing file never
    blocks brief creation (the trading loop must keep moving). Returns '' on any error."""
    try:
        return fn() or ""
    except Exception as exc:  # noqa: BLE001 - enrichment is strictly best-effort
        _log.info("brief block %s failed: %s", getattr(fn, "__name__", fn), exc)
        return ""

_default_reports = (
    Path(__file__).parent.parent.parent.parent
    / "TradingBotAgentProject"
    / "reports"
)
TRADING_REPORTS_DIR = Path(os.environ.get("TONY_REPORTS_DIR", str(_default_reports)))
TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks" / "todo"
VAULT_DIR = Path(__file__).parent.parent.parent / "vault"
BRIDGE_MD_DIR = Path(
    os.environ.get(
        "TONY_BRIDGE_DIR",
        str(Path(__file__).parent.parent.parent / "bridge" / "tony-stocks"),
    )
)
_PROCESSED_LOG = Path(__file__).parent.parent.parent / "workspace" / "logs" / "tony-bridge-processed.json"
# Date PREFIX (not anchored at end): a pure-date stem `2026-06-03` is the legacy one-a-day
# bridge; intraday bridges add a slot suffix `2026-06-03-1030` / `2026-06-03-eod`. Each
# distinct stem becomes its own Tony run, so 4+ bridges/day all ingest.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_TIER1_SYM_RE = re.compile(r"\[\[([A-Z][A-Z0-9.\-]{0,9})\]\]")

# Per-Tier-1 fan-out: when the brief has >= MIN Tier-1 tickers, also spawn one focused
# deep-dive verdict task per ticker (up to MAX, in bridge order = score desc) so each gets
# full depth without one giant task truncating. 0 = off. Healthy medium: MIN=3, MAX=6 —
# deep per-pick analysis on the conviction set, Tier-2/3 stay in the lighter combined brief.
# Fan-out the top conviction Tier-1 names into focused, complete deep-dive tasks so they
# never get truncated by the daily brief's 50-step tool cap. Capped modestly because the
# runner processes ~1 task/cycle — top-6 covers the highest-conviction set without backing
# up the queue. Tune via env; 0 disables. See the lightened daily brief (synthesis + the
# names fan-out didn't cover).
FANOUT_MIN_TIER1 = int(os.environ.get("TONY_FANOUT_MIN_TIER1", "3"))
FANOUT_MAX = int(os.environ.get("TONY_FANOUT_MAX", "20"))  # per-bridge pacing cap (cooldown gates repeats)

_REPORT_FILES = ["eod_report", "strategy_proposal", "approval_package"]
_VAULT_HISTORY_DAYS = 7


# The bot writes bridge files non-atomically; ignore one touched within this window so we never
# ingest (and permanently mark processed) a half-written file.
_QUIESCE_SECONDS = 5.0


def _load_processed() -> set:
    if not _PROCESSED_LOG.exists():
        return set()
    try:
        return set(json.loads(_PROCESSED_LOG.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        # A corrupt log used to silently return an empty set -> every bridge on disk re-spawns.
        # Warn loudly and preserve the corrupt file for inspection instead of mass-re-ingesting.
        _log.warning("tony_bridge: processed-log corrupt (%s); preserving as .corrupt", exc)
        try:
            _PROCESSED_LOG.replace(_PROCESSED_LOG.with_suffix(_PROCESSED_LOG.suffix + ".corrupt"))
        except OSError:
            pass
        return set()
    except OSError:
        return set()


def _save_processed(processed: set) -> None:
    _PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: a crash mid-write must not truncate the log into invalid JSON (which would
    # wipe all dedup history). Write a tmp file in the same dir, then os.replace() it into place.
    tmp = _PROCESSED_LOG.with_suffix(_PROCESSED_LOG.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(sorted(processed)), encoding="utf-8")
        os.replace(tmp, _PROCESSED_LOG)
    except OSError as exc:
        _log.warning("tony_bridge: processed-log save failed: %s", exc)


_HISTORY_POISON = (
    "data integrity failure", "mass exit", "flag_issue", "no tool calls",
    "returned no text summary", "data failure", "data interruption", "no new signals",
)


def _load_vault_history() -> str:
    """Read recent PRODUCTIVE Tony sessions from the vault, skipping broken-scan / no-op runs
    (their 'data integrity failure / mass exit / no signals' narrative anchors Tony into
    concluding the environment is broken and skipping his per-ticker analysis)."""
    sessions_dir = VAULT_DIR / "sessions"
    if not sessions_dir.exists():
        return "No prior sessions found."

    dated_dirs = sorted(
        [d for d in sessions_dir.iterdir() if d.is_dir()],
        reverse=True,
    )[:_VAULT_HISTORY_DAYS]

    entries = []
    for dated_dir in dated_dirs:
        for session_file in sorted(dated_dir.glob("TONY-*.md")):
            try:
                txt = session_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if any(m in txt.lower() for m in _HISTORY_POISON):
                continue  # drop poisoned / no-op runs so they don't anchor a fresh brief
            entries.append(txt)

    if not entries:
        return "No prior productive sessions — analyze today's bridge fresh on its own merits."

    return "\n\n---\n\n".join(entries[-5:])  # cap to keep context tight


def _extract_watchlist(eod_raw: str) -> str:
    """Pull watchlist from EOD report if present; return formatted section or empty string."""
    try:
        eod = json.loads(eod_raw)
        watchlist = eod.get("watchlist", [])
        if not watchlist:
            return ""
        lines = ["| Ticker | Sector | Setup | Score | Days Watched | Trigger Condition |",
                 "|--------|--------|-------|-------|--------------|-------------------|"]
        for w in watchlist:
            lines.append(
                f"| {w.get('ticker','?')} | {w.get('sector','?')} | {w.get('setup','?')} "
                f"| {w.get('score','?')} | {w.get('days_watched','?')} "
                f"| {w.get('trigger_condition','—')} |"
            )
        reasons = "\n".join(
            f"- **{w.get('ticker','?')}:** {w.get('reason','')}" for w in watchlist
        )
        return f"## Scanner Watchlist (pre-trigger)\n\n{chr(10).join(lines)}\n\n### Why the scanner is watching these\n\n{reasons}\n"
    except (json.JSONDecodeError, KeyError, TypeError):
        return ""


def _make_daily_brief(date_str: str, reports: dict[str, str]) -> None:
    task_id = f"TONY-DAILY-BRIEF-{date_str.replace('-', '')}"
    title = f"Tony Daily Brief — {date_str}"

    vault_history = _load_vault_history()

    eod = reports.get("eod_report", "{}")
    approval = reports.get("approval_package", "{}")
    watchlist_section = _extract_watchlist(eod)

    # Skip deep strategy analysis if nothing changed
    strategy_raw = reports.get("strategy_proposal", "{}")
    try:
        s = json.loads(strategy_raw)
        strategy_note = (
            "Strategy unchanged (v1→v1, no approvals). Skip deep analysis."
            if s.get("current_version") == s.get("proposed_version") and s.get("approved_count", 0) == 0
            else strategy_raw
        )
    except (json.JSONDecodeError, KeyError):
        strategy_note = strategy_raw

    watchlist_instructions = ""
    if watchlist_section:
        watchlist_instructions = """\
- Research the scanner watchlist: for each pre-trigger ticker, do a quick web search and check its vault page. Update `vault/tony-stocks/watchlist.md` with your findings.
"""

    body = f"""\
You are Tony Stocks. This is your daily analytical brief for {date_str}.

**Signal Ledger:** `vault/tony-stocks/signal-ledger.md` — read this first, update it last.

## Your Workflow

Follow the workflow in your system prompt exactly. Key focus for today:
- Check `active_symbols`, `pending_triggers`, and `weakening` count in the EOD report
- Cross-reference active symbols against the signal ledger for persistence
- Research any ticker appearing 2+ days with `web_research`
- Flag if weakening count is rising
{watchlist_instructions}
---

## Today's EOD Report

```json
{eod}
```

---
{watchlist_section}
---

## Today's Strategy

{strategy_note}

---

## Today's Approval Package

```json
{approval}
```

---

## Recent Session History (last {_VAULT_HISTORY_DAYS} days)

{vault_history}
"""

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = TASKS_DIR / f"{task_id}.md"
    task_file.write_text(
        f"---\n"
        f"task_id: {task_id}\n"
        f"assigned_agent: market_research_worker\n"
        f"status: todo\n"
        f"priority: normal\n"
        f"pod: stock_research_pod\n"
        f"task_type: market_scan_summary\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    _log.info("tony_bridge: created daily brief %s", task_id)


def _make_brief_from_bridge(slug: str, bridge_md: str) -> None:
    date_str = slug[:10]  # slug may carry an intraday slot suffix; the body shows the trading day
    _refresh_signal_ledger(slug, bridge_md)  # keep the prose ledger fresh even if the brief truncates
    task_id = f"TONY-DAILY-BRIEF-{slug.replace('-', '')}"
    title = f"Tony Brief — {slug}"

    vault_history = _load_vault_history()
    track_record = track_record_block()
    regime = _safe_block(regime_header)
    book = _safe_block(book_block)
    exec_fb = _safe_block(execution_feedback_block)
    lessons = _safe_block(lessons_block)

    body = f"""\
You are Tony Stocks. This is your daily analytical brief for {date_str}.

The scanner (TradingBotAgentProject) is the FIRST layer — scripts, charts, technical
scores. You are the SECOND layer: a research analyst who independently verifies the
data, pulls real fundamentals, reads the news, then makes YOUR OWN call on each pick.

**Signal Ledger:** `vault/tony-stocks/signal-ledger.md` — read it for persistence context.
It is now auto-maintained from the scanner bridge, so do NOT write to it.

The highest-conviction Tier-1 names get their own focused deep-dive tasks (fan-out), so you
do NOT have to research all 26 here — that just runs you out of tool budget. Prioritise:
cross-cutting synthesis, cluster risk, and the Tier-1 names fan-out did not cover.

{regime}
{book}
{exec_fb}
{track_record}

{lessons}
## Per-ticker steps (apply to the names you cover):

1. **Pull real data** — call `get_stock_data(symbol)`. The scanner's close is stale; this
   is your live price + fundamentals (P/E, revenue/earnings growth, margins, analyst target
   & rating, **next earnings date**, 52-week range). Compare it to the scanner's numbers.
2. **Verify the setup** — call `get_price_history(symbol)` for your OWN RSI/SMA/ATR/volume
   read. Confirm (or reject) the scanner's technical setup on your own indicators.
3. **Research the why** — call `get_stock_news(symbol)` first for timestamped, ticker-tagged
   headlines (the scanner can't read news — this is your edge), then `web_research(action=search)`
   to dig into any catalyst/earnings/legal item the headlines surface.
4. **Check hard events** — call `get_catalysts(symbol)` for recent SEC filings (8-K material
   events, Form 4 insider buying/selling, 13D/G stakes) + insider bias. Insider dumping or a
   surprise 8-K is a red flag the scanner can't see.
5. **Check your memory** — read `vault/tickers/TICKER.md` for prior history on this name.
6. **Decide and record** — call `write_tony_verdict(...)` with YOUR independent 0–100 score
   and a verdict: **reaffirm** (agree), **adjust** (agree, change target/stop), **override**
   (you'd trade it differently), **pass** (skip), or **close** (avoid/exit). Ground the thesis
   in the data you pulled. Red flags that should push you off the scanner's pick: analyst
   target BELOW price, earnings INSIDE the trade window, deteriorating margins, news risk.

Then, across the whole brief:
- Review each Cluster Risk Flag — say whether the concentration changes any verdict.
- Write 1–3 cross-cutting `write_tony_insight` notes (sector/macro context, not per-pick).
- Update ticker memory and sector-rotation notes. (The signal ledger is auto-maintained — leave it.)

---

## Scanner Bridge — {date_str}

{bridge_md}

---

## Recent Session History (last {_VAULT_HISTORY_DAYS} days)

{vault_history}
"""

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = TASKS_DIR / f"{task_id}.md"
    task_file.write_text(
        f"---\n"
        f"task_id: {task_id}\n"
        f"assigned_agent: market_research_worker\n"
        f"status: todo\n"
        f"priority: normal\n"
        f"pod: stock_research_pod\n"
        f"task_type: market_scan_summary\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    _log.info("tony_bridge: created daily brief %s (markdown bridge)", task_id)

    _fanout_deepdives(slug, bridge_md)


def _make_intraday_brief(slug: str, bridge_md: str) -> None:
    """Intraday slots (10:30 / 13:00 / 15:30 / EOD ET) get a FULL deep-dive — same per-ticker
    research depth as the morning brief, with intraday framing that also re-assesses open
    holdings. With only ~4-5 handoffs a day there is ample time between them for real analysis,
    and an `adjust` here re-prices the live stop/target on a position Tony already holds."""
    date_str = slug[:10]
    _refresh_signal_ledger(slug, bridge_md)  # keep the prose ledger fresh through the day
    slot = slug[11:] or "intraday"  # e.g. "2026-06-02T1030" -> "1030"
    task_id = f"TONY-INTRADAY-{slug.replace('-', '').replace('T', '-')}"
    title = f"Tony Intraday Deep-Dive — {date_str} {slot} ET"

    vault_history = _load_vault_history()
    track_record = track_record_block()
    regime = _safe_block(regime_header)
    book = _safe_block(book_block)
    exec_fb = _safe_block(execution_feedback_block)
    lessons = _safe_block(lessons_block)

    body = f"""\
You are Tony Stocks. This is your intraday deep-dive for {date_str} (slot {slot} ET). Markets are
open 09:30–16:00 ET; you already hold positions and made earlier calls today. This is a FULL
re-analysis with fresh live data — not a skim.

The scanner (TradingBotAgentProject) is the FIRST layer — scripts, charts, technical scores.
You are the SECOND layer: a research analyst who independently verifies the data, pulls real
fundamentals, reads the news, then makes YOUR OWN call on each pick and on every open position.

**Signal Ledger:** `vault/tony-stocks/signal-ledger.md` — read this first, update it last.

{regime}
{book}
{exec_fb}
{track_record}

{lessons}

## Your Workflow — for EACH Tier 1 ticker (and every name you currently HOLD), do all of this:

1. **Pull real data** — call `get_stock_data(symbol)` for the live price + fundamentals (P/E,
   revenue/earnings growth, margins, analyst target & rating, **next earnings date**, 52-week
   range). The scanner's close is stale; compare it to the live numbers.
2. **Verify the setup** — call `get_price_history(symbol)` for your OWN RSI/SMA/ATR/volume read.
   Confirm or reject the scanner's technical setup on your own indicators.
3. **Research the why** — call `get_stock_news(symbol)` first for fresh timestamped, ticker-tagged
   headlines (your edge over the scanner), then `web_research(action=search)` for anything that
   moved since your last pass.
4. **Check hard events** — call `get_catalysts(symbol)` for recent SEC filings (8-K, Form 4
   insider activity, 13D/G) + insider bias — a surprise 8-K or insider dumping overrides a clean chart.
5. **Check your memory** — read `vault/tickers/TICKER.md` for prior history on this name.
6. **Decide and record** — call `write_tony_verdict(...)` with YOUR independent 0–100 score and a
   verdict: **reaffirm** (hold as-is), **adjust** (agree but MOVE your target/stop — for a name
   you already hold this RE-PRICES your live protective stop/target), **override** (trade it
   differently), **pass** (skip), or **close** (exit/avoid — closes the position). Red flags that
   push you off a pick: analyst target BELOW price, earnings INSIDE the trade window, deteriorating
   margins, news risk. For positions you HOLD: explicitly re-assess each one — tighten or raise the
   stop/target with `adjust` as the setup evolves, or `close` if the thesis broke or risk line hit.

Then, across the whole brief:
- Review each Cluster Risk Flag — say whether the concentration changes any verdict.
- Write 1–3 cross-cutting `write_tony_insight` notes (sector/macro context, not per-pick).
- Update ticker memory and sector-rotation notes. (The signal ledger is auto-maintained — leave it.)

---

## Intraday Scanner Bridge — {date_str} {slot} ET

{bridge_md}

---

## Recent Session History (last {_VAULT_HISTORY_DAYS} days)

{vault_history}
"""

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    (TASKS_DIR / f"{task_id}.md").write_text(
        f"---\n"
        f"task_id: {task_id}\n"
        f"assigned_agent: market_research_worker\n"
        f"status: todo\n"
        f"priority: high\n"
        f"pod: stock_research_pod\n"
        f"task_type: market_scan_intraday\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    _log.info("tony_bridge: created intraday update %s", task_id)

    _fanout_deepdives(slug, bridge_md)


def _latest_bridge_md() -> tuple[str, str]:
    """(slug, content) of the most recent bot bridge, or ('', '') if none exist yet."""
    if not BRIDGE_MD_DIR.exists():
        return "", ""
    files = sorted([f for f in BRIDGE_MD_DIR.glob("*.md") if _DATE_RE.match(f.stem)])
    if not files:
        return "", ""
    try:
        return files[-1].stem, files[-1].read_text(encoding="utf-8")
    except OSError:
        return "", ""


def make_preopen_deepdive(date_str: str) -> None:
    """Pre-open (~09:25 ET, right after the reset) deep-dive so Tony walks into the 09:30 open
    with fresh researched calls instead of waiting for the bot's first intraday bridge (which can
    land late morning). He re-evaluates every open position first, then reviews the latest
    bridge's watchlist."""
    task_id = f"TONY-PREOPEN-{date_str.replace('-', '')}"
    # Idempotent per day: a manual re-run of preopen_reset.py must not clobber an in-flight
    # deep-dive or spawn a duplicate after the first was consumed.
    tasks_root = TASKS_DIR.parent if TASKS_DIR.name == "todo" else TASKS_DIR
    for sub in ("todo", "in_progress", "done", "failed"):
        if (tasks_root / sub / f"{task_id}.md").exists() or (TASKS_DIR / f"{task_id}.md").exists():
            _log.info("tony_bridge: pre-open deep-dive %s already exists — skipping", task_id)
            return
    title = f"Tony Pre-Open Deep-Dive — {date_str}"
    vault_history = _load_vault_history()
    slug, bridge_md = _latest_bridge_md()
    regime = _safe_block(regime_header)
    book = _safe_block(book_block)
    exec_fb = _safe_block(execution_feedback_block)
    lessons = _safe_block(lessons_block)
    bridge_section = (
        f"## Latest scanner bridge ({slug}) — your watchlist universe\n\n{bridge_md}"
        if bridge_md else
        "## No fresh scanner bridge yet — focus entirely on re-evaluating your open positions."
    )

    body = f"""\
You are Tony Stocks. This is your PRE-OPEN deep-dive for {date_str}, run right before the 09:30
ET open. Goal: walk into the open with fresh, researched calls — do NOT wait for the first
intraday bridge.

The scanner (TradingBotAgentProject) is the FIRST layer; you are the SECOND — independently
verify the data, pull real fundamentals, read the news, then make YOUR OWN call.

**Signal Ledger:** `vault/tony-stocks/signal-ledger.md` — read this first, update it last.

{regime}
{book}
{exec_fb}
{lessons}
## Step 1 — re-evaluate EVERY position you currently hold (do this first)
Check your live book. For EACH name you hold:
1. `get_stock_data(symbol)` — live/pre-market price + fundamentals + next earnings date.
2. `get_price_history(symbol)` — your own RSI/SMA/ATR/volume read.
3. `web_research(action=search)` — overnight news/catalysts.
4. `write_tony_verdict(...)` — **reaffirm** (hold as-is), **adjust** (MOVE your target/stop — for a
   held name this RE-PRICES your live protective stop/target), or **close** (exit if the thesis
   broke or the risk line is hit).

## Step 2 — review the watchlist below for fresh setups
For each Tier 1 name you do NOT already hold, run the same get_stock_data + get_price_history +
web_research, then `write_tony_verdict(...)` — reaffirm/adjust/override to enter (becomes a GTC
bracket) or pass. Never re-buy a name you already hold.

Then write 1–3 cross-cutting `write_tony_insight` notes and update the signal ledger + ticker memory.

---

{bridge_section}

---

## Recent Session History (last {_VAULT_HISTORY_DAYS} days)

{vault_history}
"""

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    (TASKS_DIR / f"{task_id}.md").write_text(
        f"---\n"
        f"task_id: {task_id}\n"
        f"assigned_agent: market_research_worker\n"
        f"status: todo\n"
        f"priority: high\n"
        f"pod: stock_research_pod\n"
        f"task_type: market_scan_intraday\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    _log.info("tony_bridge: created pre-open deep-dive %s", task_id)


def _extract_tier1_symbols(md: str) -> list[str]:
    """Pull [[TICKER]] names from the Tier 1 section only — anchored on the section heading and
    bounded by the next section heading. Bare substring splitting ('Tier 1'..'Tier 2') over-
    captured: a bridge with no Tier-2 section, or prose merely mentioning 'Tier 1', dragged
    Tier-3/watchlist names into the fan-out. The bound is the next level-2 (`## `) heading, so
    the `### [[SYM]]` ticker sub-headings inside the section are preserved."""
    m = re.search(r"^#{1,3}\s*Tier\s*1\b", md, re.M)
    if not m:
        return []
    section = md[m.end():]
    nxt = re.search(r"^##\s", section, re.M)  # next section (e.g. ## Tier 2); not ### tickers
    if nxt:
        section = section[:nxt.start()]
    return list(dict.fromkeys(_TIER1_SYM_RE.findall(section)))


# Same symbol grammar as _TIER1_SYM_RE — the two previously disagreed ([A-Z0-9.\-]+ vs
# [A-Z][A-Z0-9.\-]{0,9}), so the ledger and the fan-out could diverge on the same bridge.
_TIER1_BLOCK_RE = re.compile(
    r"###\s*\[\[([A-Z][A-Z0-9.\-]{0,9})\]\]\s*\n(.*?)(?=\n###|\n##\s|\Z)", re.DOTALL)


def _signal_ledger_path():
    # Resolve from VAULT_DIR at call time (not a module constant) so tests that monkeypatch
    # VAULT_DIR are isolated — a bound constant would make every test write the real vault.
    return VAULT_DIR / "tony-stocks" / "signal-ledger.md"


def _parse_bridge_signals(bridge_md: str) -> dict:
    """Extract the scanner's ticker rows from a bridge for the signal ledger: Tier 1 = rich
    `### [[SYM]]` detail blocks (3+ days); Tier 2/3 = lighter table rows (2-day / 1-day)."""
    tier1 = []
    for m in _TIER1_BLOCK_RE.finditer(bridge_md):
        sym, block = m.group(1), m.group(2)
        days = re.search(r"Days active:\s*(\d+)", block)
        score = re.search(r"Score:\s*([\d.]+)", block)
        setup = re.search(r"Setup:\s*([^\n|]+)", block)
        trig = re.search(r"Entry triggered:\s*(\w+)", block)
        target = re.search(r"Target:\s*\$?([\d.]+)", block)
        stop = re.search(r"Stop:\s*\$?([\d.]+)", block)
        close = re.search(r"Last close:\s*\$?([\d.]+)", block)
        rr = re.search(r"R/R:\s*([\d.]+:?[\d.]*)", block)
        tier1.append({"symbol": sym, "days": int(days.group(1)) if days else 0,
                      "score": score.group(1) if score else "",
                      "setup": setup.group(1).strip() if setup else "",
                      "triggered": bool(trig and trig.group(1).lower() == "yes"),
                      "target": target.group(1) if target else "",
                      "stop": stop.group(1) if stop else "",
                      "close": close.group(1) if close else "",
                      "rr": rr.group(1) if rr else ""})
    newer = []
    seen = {t["symbol"] for t in tier1}  # a symbol in two tiers must not double-enter the ledger
    for tier_name, days in (("Tier 2", 2), ("Tier 3", 1)):
        # Anchor on the section HEADING and bound by the next section — bare split(tier_name)
        # mis-sliced on prose like "compared to Tier 2 names" (the same bug Tier 1 was hardened for).
        hdr = re.search(rf"^#{{1,3}}\s*{tier_name}\b", bridge_md, re.M)
        if not hdr:
            continue
        after = bridge_md[hdr.end():]
        nxt = re.search(r"^##\s", after, re.M)
        body = after[:nxt.start()] if nxt else after
        for row in body.splitlines():
            if not row.strip().startswith("|"):
                continue
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            sm = _TIER1_SYM_RE.search(cells[0]) if cells else None
            if not sm or sm.group(1) in seen:
                continue
            seen.add(sm.group(1))
            score = cells[1] if len(cells) > 1 and re.match(r"^[\d.]+$", cells[1]) else ""
            close = cells[3].lstrip("$") if len(cells) > 3 and re.match(r"^\$?[\d.]+$", cells[3]) else ""
            rr = cells[6] if len(cells) > 6 else ""
            newer.append({"symbol": sm.group(1), "days": days, "score": score,
                          "setup": cells[2] if len(cells) > 2 else "", "triggered": False,
                          "target": "", "stop": "", "close": close, "rr": rr})
    return {"tier1": tier1, "newer": newer}


def _refresh_signal_ledger(slug: str, bridge_md: str) -> bool:
    """Deterministically rebuild signal-ledger.md from the authoritative scanner bridge so the
    prose ledger is never stale — even when Tony's brief truncates before its 'update ledger'
    step (the 50-step tool cap is exhausted by per-ticker research on a big slate). The signal
    tables + day counts come straight from the bridge; Tony's qualitative calls live in the
    live verdict book, not here. No-op (returns False) when the bridge has no parseable signals,
    so a malformed bridge never wipes the ledger."""
    sig = _parse_bridge_signals(bridge_md)
    persistent = [s for s in sig["tier1"] if s["days"] >= 3]
    active = [s for s in sig["tier1"] if s["days"] < 3] + sig["newer"]
    if not persistent and not active:
        return False
    date_str = slug[:10]
    # Monotonic: never move the ledger backwards. Bridges are ingested newest-first, so when
    # several are unprocessed (e.g. after a restart) an older one must not clobber the fresher
    # ledger. Compare at SLOT granularity (full slug), not date — within one day the slots sort
    # daily < T1030 < T1300 < T1530 < T1600 < Teod, so an earlier slot can't overwrite eod.
    ledger = _signal_ledger_path()
    existing = ""
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            m = re.match(r"<!--\s*bridge-slug:\s*(\S+)\s*-->", line)
            if m:
                existing = m.group(1)
                break
            if line.lower().startswith("last updated:"):  # legacy ledger w/o marker -> date only
                existing = line.split(":", 1)[1].strip()[:10]
                break
    except OSError:
        pass
    if existing and slug < existing:
        _log.info("tony_bridge: skip ledger refresh — bridge %s older than ledger %s", slug, existing)
        return False
    lines = [
        "---", "tags: [tony]", "---", "",
        f"<!-- bridge-slug: {slug} -->",
        "# Tony Stocks — Signal Ledger", "",
        "Auto-maintained from the scanner bridge on each ingestion. Tony's qualitative calls "
        "live in the live verdict book (dashboard Paper Book / Tony's Calls), not in this file.",
        f"Last updated: {date_str}", "", "---", "",
        "## Persistent Signals (3+ days)", "",
        "| Ticker | Days Active | Setup Type | Score | Target | Stop | R/R | Status |",
        "|--------|-------------|-----------|-------|--------|------|-----|--------|",
    ]
    for s in sorted(persistent, key=lambda x: x["days"], reverse=True):
        tgt = f"${s['target']}" if s.get("target") else ""
        stp = f"${s['stop']}" if s.get("stop") else ""
        lines.append(f"| {s['symbol']} | {s['days']} | {s['setup']} | {s['score']} | {tgt} | "
                     f"{stp} | {s.get('rr', '')} | {'triggered' if s['triggered'] else 'watching'} |")
    lines += ["", "## Active Signals", "",
              "| Ticker | Days Active | Setup Type | Score | R/R |",
              "|--------|-------------|-----------|-------|-----|"]
    for s in sorted(active, key=lambda x: x["days"], reverse=True):
        lines.append(f"| {s['symbol']} | {s['days']} | {s['setup']} | {s['score']} | {s.get('rr', '')} |")
    lines.append("")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("\n".join(lines), encoding="utf-8")
    _log.info("tony_bridge: refreshed signal-ledger.md (%d persistent, %d active) for %s",
              len(persistent), len(active), date_str)
    return True


def _spawn_ticker_task(slug: str, sym: str) -> None:
    date_str = slug[:10]
    task_id = f"TONY-TKR-{sym}-{slug.replace('-', '')}"
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    (TASKS_DIR / f"{task_id}.md").write_text(
        f"---\n"
        f"task_id: {task_id}\n"
        f"assigned_agent: market_research_worker\n"
        f"status: todo\n"
        f"priority: normal\n"
        f"pod: stock_research_pod\n"
        f"task_type: ticker_deepdive\n"
        f"---\n\n"
        f"# Deep-dive verdict — {sym} ({date_str})\n\n"
        f"Produce ONE structured verdict for **{sym}**. Steps:\n"
        f"1. `get_stock_data('{sym}')` — live price + fundamentals + earnings date.\n"
        f"2. `get_price_history('{sym}')` — your own RSI/SMA/ATR/volume read.\n"
        f"3. `web_research(action=search)` — news/catalysts.\n"
        f"4. `write_tony_verdict(...)` — your independent score + verdict + (for adjust/override) "
        f"your own target & stop.\n"
        f"5. If you HOLD {sym}: re-test the thesis — reaffirm, `adjust` (re-prices your live "
        f"stop/target), or `close`. Exits and re-prices execute even when the book is FULL.\n"
        f"6. If you do NOT hold it and it's a real setup, ALSO call "
        f"`queue_research_candidate('{sym}', score, ..., proposed_target, proposed_stop)` — a full "
        f"book/cap means an entry verdict can never fill and is wiped at the 09:25 flush, but the "
        f"queue SURVIVES the flush and is re-validated at the next open into freed slots.\n"
        f"Then append your findings to `vault/tickers/{sym}.md`.\n",
        encoding="utf-8",
    )
    try:  # cooldown ledger: stamp the spawn so the same name isn't re-fanned every bridge
        from runner.ledger.deepdive_ledger import mark_deepdived
        mark_deepdived(sym)
    except Exception:
        pass
    _log.info("tony_bridge: fan-out ticker task %s", task_id)


def _held_symbols_stale_first() -> list:
    """Open-position symbols ordered stalest-deep-dive first (never-dived lead), from the book
    cache + the cooldown ledger. With a FULL book, re-examining what we HOLD is the research that
    can still ACT (adjust/close execute regardless of the entry cap), and names that aged out of
    the bot's bridge otherwise get no intraday re-evaluation at all. Fail-soft to empty."""
    try:
        from runner.tools.tony_book import read_book_cache
        from runner.ledger.deepdive_ledger import _read as _dd_stamps
        syms = [p.get("symbol") for p in (read_book_cache() or {}).get("positions", [])
                if p.get("symbol")]
        stamps = _dd_stamps()
        return sorted(syms, key=lambda s: stamps.get(s, ""))
    except Exception:
        return []


def _fanout_deepdives(slug: str, bridge_md: str) -> None:
    """Spawn deep-dive tasks for the WHOLE universe — every scanned name (Tier 1 + Tier 2/3 via
    `newer`) PLUS held positions (stalest re-check first) PLUS Tony's own originated ideas —
    cooldown-gated so the SAME names aren't re-graded every bridge. Held names lead: with a full
    book they're the only research that can still act (adjust/close are never cap-gated).
    FANOUT_MAX paces queue growth per bridge (NOT a coverage cap; the cooldown plus
    successive bridges sweep the rest). No-op unless the bridge carries >= FANOUT_MIN_TIER1 Tier-1
    names (i.e. a substantial bridge). Fail-soft — never breaks ingestion."""
    if not FANOUT_MIN_TIER1:
        return
    try:
        sig = _parse_bridge_signals(bridge_md)
        tier1 = [s.get("symbol") for s in sig.get("tier1", []) if s.get("symbol")]
        if len(tier1) < FANOUT_MIN_TIER1:
            return
        from runner.ledger.deepdive_ledger import due_for_deepdive
        held_list = _held_symbols_stale_first()
        held = {(s or "").strip().upper() for s in held_list}
        universe = list(held_list)
        universe += [s.get("symbol") for s in sig.get("tier1", []) + sig.get("newer", [])]
        try:
            from runner.bridge.research_wave import _recent_idea_symbols
            universe += _recent_idea_symbols()
        except Exception:
            pass
        # Adaptive spend throttle: scale NEW-NAME research to OPEN CAPACITY. At/near the position
        # cap a new name can't enter anyway (its queue entry competes for ~0 slots), so don't burn
        # API $ on 20 of them per bridge — keep a small floor trickling into the flush-proof queue
        # so the BEST few are ready when exits free slots, and auto-scale back up as slots open.
        # Held re-checks always keep the full pace (adjust/close act regardless of the cap).
        try:
            from runner.ledger.alpaca_paper import MAX_OPEN_POSITIONS
            slots_free = max(0, MAX_OPEN_POSITIONS - len(held))
        except Exception:
            slots_free = FANOUT_MAX
        floor = int(os.environ.get("TONY_NEWNAME_FANOUT_FLOOR", "2"))
        new_budget = min(FANOUT_MAX, max(floor, slots_free))
        seen: set = set()
        spawned = new_spawned = 0
        for s in universe:
            s = (s or "").strip().upper()
            if not s or s in seen:
                continue
            seen.add(s)
            if not due_for_deepdive(s):
                continue
            if s not in held and new_spawned >= new_budget:
                continue  # at/near cap: skip extra new names, keep sweeping held re-checks
            _spawn_ticker_task(slug, s)
            spawned += 1
            new_spawned += 0 if s in held else 1
            if spawned >= FANOUT_MAX:
                break
    except Exception as exc:
        _log.warning("deep-dive fan-out skipped: %s", exc)


def _scan_markdown_bridge(processed: set) -> None:
    """Primary source: rich markdown bridges the trading bot drops in bridge/tony-stocks/."""
    if not BRIDGE_MD_DIR.exists():
        return

    md_files = sorted(
        [f for f in BRIDGE_MD_DIR.glob("*.md") if _DATE_RE.match(f.stem)],
        reverse=True,
    )

    now = time.time()
    for md_file in md_files:
        slug = md_file.stem
        date_str = slug[:10]
        # Pure-date bridge keeps the legacy key so it still dedups against the JSON fallback;
        # an intraday slot keys on its full stem so each slot fires its own run.
        key = f"{date_str}/daily_brief" if slug == date_str else f"{slug}/brief"
        if key in processed:
            continue
        try:
            # Quiescence gate: don't read a bridge the bot may still be writing — ingesting a
            # truncated file and then marking it processed would lock in the partial version.
            if now - md_file.stat().st_mtime < _QUIESCE_SECONDS:
                continue
            bridge_md = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            _log.warning("tony_bridge: could not read %s: %s", md_file, exc)
            continue
        if not bridge_md.strip():
            continue
        try:
            if slug == date_str:
                _make_brief_from_bridge(slug, bridge_md)   # full morning/EOD deep analysis
            else:
                _make_intraday_brief(slug, bridge_md)      # light intraday update, not a re-run
        except Exception as exc:
            # One malformed bridge must not abort ingestion of the others this cycle.
            _log.warning("tony_bridge: failed to process %s: %s", md_file, exc)
            continue
        processed.add(key)
        _save_processed(processed)  # persist per-spawn so a crash mid-scan can't double-spawn


def _scan_json_reports(processed: set) -> None:
    """Fallback source: legacy JSON reports from TradingBotAgentProject/reports/<date>/."""
    if not TRADING_REPORTS_DIR.exists():
        return

    dated_dirs = sorted(
        [d for d in TRADING_REPORTS_DIR.iterdir() if d.is_dir() and d.name[:4].isdigit()],
        reverse=True,
    )

    for dated_dir in dated_dirs:
        date_str = dated_dir.name
        key = f"{date_str}/daily_brief"
        if key in processed:
            continue

        # Collect whichever reports exist for this date
        reports: dict[str, str] = {}
        for report_name in _REPORT_FILES:
            json_file = dated_dir / f"{report_name}.json"
            if json_file.exists():
                try:
                    reports[report_name] = json_file.read_text(encoding="utf-8")
                except OSError as exc:
                    _log.warning("tony_bridge: could not read %s: %s", json_file, exc)

        if not reports:
            continue

        try:
            _make_daily_brief(date_str, reports)
        except Exception as exc:
            _log.warning("tony_bridge: failed to process reports for %s: %s", date_str, exc)
            continue
        processed.add(key)
        _save_processed(processed)  # persist per-spawn so a crash mid-scan can't double-spawn


def scan_and_process() -> None:
    processed = _load_processed()
    _scan_markdown_bridge(processed)
    _scan_json_reports(processed)
    _save_processed(processed)
