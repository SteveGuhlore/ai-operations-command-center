# runner/scheduler/daily_jobs.py
import json
from datetime import datetime, date
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "scheduler-state.json"


def _read() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def scout_due(interval_hours: float = 2.0) -> bool:
    last = _read().get("last_scout")
    if not last:
        return True
    try:
        elapsed = datetime.now() - datetime.fromisoformat(last)
    except ValueError:
        return True
    return elapsed.total_seconds() >= interval_hours * 3600


def mark_scout_ran() -> None:
    data = _read()
    data["last_scout"] = datetime.now().isoformat()
    _write(data)


def daily_learning_due(hour_after: int = 2) -> bool:
    """True once per day, only after the given hour (local)."""
    data = _read()
    today = str(date.today())
    if data.get("last_learning_date") == today:
        return False
    return datetime.now().hour >= hour_after


def mark_learning_ran() -> None:
    data = _read()
    data["last_learning_date"] = str(date.today())
    _write(data)


def tony_self_review_due(interval_days: float = 7.0) -> bool:
    """True once per ~week — Tony grades his own verdicts vs outcomes and learns."""
    last = _read().get("last_tony_self_review")
    if not last:
        return True
    try:
        elapsed = datetime.now() - datetime.fromisoformat(last)
    except ValueError:
        return True
    return elapsed.total_seconds() >= interval_days * 86400


def mark_tony_self_review_ran() -> None:
    data = _read()
    data["last_tony_self_review"] = datetime.now().isoformat()
    _write(data)


def preopen_done_today() -> bool:
    """True once the pre-open reset has run today (set by either the 09:25 cron or the runner
    backstop), so the two never double-run and the missing-flush alert stays quiet."""
    return _read().get("last_preopen_date") == str(date.today())


def mark_preopen_ran() -> None:
    data = _read()
    data["last_preopen_date"] = str(date.today())
    _write(data)


def alert_due(key: str) -> bool:
    """True once per day per alert key — a persistent issue nags at most daily, not every cycle."""
    return _read().get(f"alert_{key}") != str(date.today())


def mark_alert_ran(key: str) -> None:
    data = _read()
    data[f"alert_{key}"] = str(date.today())
    _write(data)


def health_alert_due(interval_hours: float = 1.0) -> bool:
    last = _read().get("last_health_check")
    if not last:
        return True
    try:
        elapsed = datetime.now() - datetime.fromisoformat(last)
    except ValueError:
        return True
    return elapsed.total_seconds() >= interval_hours * 3600


def mark_health_check_ran() -> None:
    data = _read()
    data["last_health_check"] = datetime.now().isoformat()
    _write(data)


def weekly_sage_due() -> bool:
    """True once on Sundays (weekday 6) if not already run today."""
    data = _read()
    today = str(date.today())
    if datetime.now().weekday() != 6:
        return False
    return data.get("last_sage_date") != today


def mark_sage_ran() -> None:
    data = _read()
    data["last_sage_date"] = str(date.today())
    _write(data)
