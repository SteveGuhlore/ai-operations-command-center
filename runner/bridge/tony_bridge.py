import json
import logging
import os
from pathlib import Path

_log = logging.getLogger(__name__)

_default_reports = (
    Path(__file__).parent.parent.parent.parent
    / "TradingBotAgentProject"
    / "reports"
)
TRADING_REPORTS_DIR = Path(os.environ.get("TONY_REPORTS_DIR", str(_default_reports)))
TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks" / "todo"
VAULT_DIR = Path(__file__).parent.parent.parent / "vault"
_PROCESSED_LOG = Path(__file__).parent.parent.parent / "workspace" / "logs" / "tony-bridge-processed.json"

_REPORT_FILES = ["eod_report", "strategy_proposal", "approval_package"]
_VAULT_HISTORY_DAYS = 7


def _load_processed() -> set:
    if not _PROCESSED_LOG.exists():
        return set()
    try:
        return set(json.loads(_PROCESSED_LOG.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_processed(processed: set) -> None:
    _PROCESSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    _PROCESSED_LOG.write_text(json.dumps(sorted(processed)), encoding="utf-8")


def _load_vault_history() -> str:
    """Read the last N days of Tony's session outputs from the vault."""
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
                entries.append(session_file.read_text(encoding="utf-8"))
            except OSError:
                pass

    if not entries:
        return "No prior Tony sessions found."

    return "\n\n---\n\n".join(entries[-10:])  # cap at 10 entries to keep context tight


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


def scan_and_process() -> None:
    if not TRADING_REPORTS_DIR.exists():
        return

    processed = _load_processed()

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

        _make_daily_brief(date_str, reports)
        processed.add(key)

    _save_processed(processed)
