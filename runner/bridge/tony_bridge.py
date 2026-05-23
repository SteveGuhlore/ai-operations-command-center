import json
import logging
import os
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)

_default_reports = (
    Path(__file__).parent.parent.parent.parent
    / "TradingBotAgentProject"
    / "reports"
)
TRADING_REPORTS_DIR = Path(os.environ.get("TONY_REPORTS_DIR", str(_default_reports)))
TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks" / "todo"
_PROCESSED_LOG = Path(__file__).parent.parent.parent / "workspace" / "logs" / "tony-bridge-processed.json"

# Maps report filename → (task_type, title_template, body_template)
TASK_TEMPLATES = {
    "eod_report": (
        "market_scan_summary",
        "Tony EOD Report — {date}",
        (
            "Analyze the following end-of-day stock scanner report from Tony Stocks.\n\n"
            "Your job:\n"
            "1. Identify the top 3-5 momentum signals from the scan\n"
            "2. Note any risk flags or unusual patterns\n"
            "3. Summarize overall market conditions suggested by the data\n"
            "4. Call `write_tony_insight` with your key finding (1-3 sentences, high signal-to-noise)\n\n"
            "## EOD Report Data\n\n```json\n{content}\n```"
        ),
    ),
    "strategy_proposal": (
        "strategy_review",
        "Tony Strategy Proposal — {date}",
        (
            "Review the following strategy proposal from Tony Stocks.\n\n"
            "Your job:\n"
            "1. Summarize what changes are being proposed and why\n"
            "2. Flag any concerns or risks with the proposal\n"
            "3. Note whether the proposal looks sound based on the data\n"
            "4. Call `write_tony_insight` with a one-sentence verdict\n\n"
            "## Strategy Proposal Data\n\n```json\n{content}\n```"
        ),
    ),
    "approval_package": (
        "watchlist_review",
        "Tony Approval Package — {date}",
        (
            "Review the following approval package from Tony Stocks.\n\n"
            "Your job:\n"
            "1. List what suggestions are pending decision\n"
            "2. Note which look worth approving vs skipping\n"
            "3. Call `write_tony_insight` with your recommendation\n\n"
            "## Approval Package Data\n\n```json\n{content}\n```"
        ),
    ),
}


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


def _make_task(date_str: str, report_name: str, content: str) -> None:
    if report_name not in TASK_TEMPLATES:
        return

    task_type, title_tpl, body_tpl = TASK_TEMPLATES[report_name]
    task_id = f"TONY-{report_name.upper().replace('_', '-')}-{date_str.replace('-', '')}"
    title = title_tpl.format(date=date_str)
    body = body_tpl.format(date=date_str, content=content)

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = TASKS_DIR / f"{task_id}.md"

    task_file.write_text(
        f"---\n"
        f"task_id: {task_id}\n"
        f"assigned_agent: debug_worker\n"
        f"status: todo\n"
        f"priority: normal\n"
        f"pod: stock_research_pod\n"
        f"task_type: {task_type}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    _log.info("tony_bridge: created task %s", task_id)


def scan_and_process() -> None:
    if not TRADING_REPORTS_DIR.exists():
        return

    processed = _load_processed()

    # Walk dated subdirectories newest-first
    dated_dirs = sorted(
        [d for d in TRADING_REPORTS_DIR.iterdir() if d.is_dir() and d.name[:4].isdigit()],
        reverse=True,
    )

    for dated_dir in dated_dirs:
        date_str = dated_dir.name
        for report_name in TASK_TEMPLATES:
            json_file = dated_dir / f"{report_name}.json"
            if not json_file.exists():
                continue

            key = f"{date_str}/{json_file.name}"
            if key in processed:
                continue

            try:
                content = json_file.read_text(encoding="utf-8")
                _make_task(date_str, report_name, content)
                processed.add(key)
            except OSError as exc:
                _log.warning("tony_bridge: could not read %s: %s", json_file, exc)

    _save_processed(processed)
