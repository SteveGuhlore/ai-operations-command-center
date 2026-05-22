import json
from pathlib import Path

BRIDGE_DIR = Path(__file__).parent.parent.parent / "bridge" / "tony-stocks"
TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks" / "todo"

_PROCESSED_LOG = Path(__file__).parent.parent.parent / "workspace" / "logs" / "tony-bridge-processed.json"

TASK_TEMPLATES = {
    "scanner": (
        "market_scan_summary",
        "Scanner Summary — {date}",
        "Summarise the following scanner output. Identify top setups, note momentum signals, and produce a brief research note.\n\n{content}",
    ),
    "watchlist": (
        "watchlist_review",
        "Watchlist Review — {date}",
        "Review the following watchlist data. Note which tickers are showing strength or weakness and summarise key observations.\n\n{content}",
    ),
    "paper-trade": (
        "paper_trade_journal_summary",
        "Paper Trade Journal — {date}",
        "Summarise the following paper trade journal entries. Note wins, losses, and lessons.\n\n{content}",
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


def process_bridge_file(path: Path) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    file_type = data.get("type", "")
    if not file_type:
        stem = path.stem
        for key in TASK_TEMPLATES:
            if stem.startswith(key):
                file_type = key
                break

    if file_type not in TASK_TEMPLATES:
        return

    task_type, title_tpl, body_tpl = TASK_TEMPLATES[file_type]
    date_str = data.get("date", path.stem.split("-", 1)[-1] if "-" in path.stem else "unknown")
    content = json.dumps(data, indent=2)

    task_id = f"TONY-{file_type.upper()}-{date_str.replace('-', '')}"
    title = title_tpl.format(date=date_str)
    body = body_tpl.format(date=date_str, content=content)

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = TASKS_DIR / f"{task_id}-tony-bridge.md"

    task_file.write_text(
        f"---\ntask_id: {task_id}\nassigned_agent: debug_worker\nstatus: todo\n"
        f"priority: normal\npod: stock_research_pod\ntask_type: {task_type}\n---\n\n"
        f"# {title}\n\n## Goal\n{body}\n",
        encoding="utf-8",
    )


def scan_and_process() -> None:
    if not BRIDGE_DIR.exists():
        return
    processed = _load_processed()
    for f in sorted(BRIDGE_DIR.glob("*.json")):
        if f.name not in processed:
            process_bridge_file(f)
            processed.add(f.name)
    _save_processed(processed)
