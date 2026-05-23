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


def _make_daily_brief(date_str: str, reports: dict[str, str]) -> None:
    task_id = f"TONY-DAILY-BRIEF-{date_str.replace('-', '')}"
    title = f"Tony Daily Brief — {date_str}"

    vault_history = _load_vault_history()

    eod = reports.get("eod_report", "{}")
    strategy = reports.get("strategy_proposal", "{}")
    approval = reports.get("approval_package", "{}")

    body = f"""\
You are Tony Stocks. This is your daily analytical brief for {date_str}.

## Your Workflow

**Step 1 — Read holistically.** Read all three reports below as a unified picture. Do not summarize each one separately.

**Step 2 — Identify top signals.** Pick the 2-3 most interesting signals, setups, or decisions from today's data. Look for: highest momentum scores, strategy changes, pending approvals that look significant.

**Step 3 — Web research each signal.** For each of your top picks, call `web_research` to find the news, catalyst, or macro driver behind it. Search for "[ticker] news today" or "[sector] catalyst [date]". Add what you find to your analysis.

**Step 4 — Check for historical patterns.** Review the recent session history below. Has this signal or setup appeared before? Did it follow through? Note any recurring patterns.

**Step 5 — Write insights.** Call `write_tony_insight` 1-3 times with your most valuable findings. Be specific — include tickers, what the signal is, and what the external catalyst is. Set confidence based on how much evidence you have.

**Step 6 — Spawn downstream task (if warranted).** If today's signals are strong enough to share, call `create_task` to create a `marketing_worker` task to package the insights into newsletter or social content.

---

## Today's EOD Report

```json
{eod}
```

---

## Today's Strategy Proposal

```json
{strategy}
```

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
