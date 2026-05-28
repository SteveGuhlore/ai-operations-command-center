# runner/scheduler/spawn_gate.py
"""Central spawn-cadence enforcement.

Decides whether a recurring task may be (re-)spawned right now, based on the
per-agent / per-task-type rules in config/spawn-schedules.yaml. State is
persisted to workspace/ledger/spawn-history.json so cooldowns survive runner
restarts. See that config file for the matching rules and available knobs.

Only keys present in the config are constrained; an unmatched (agent, task_type)
is always allowed, so one-off follow-up tasks are never throttled.
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from runner.config import load_spawn_schedules

LEDGER_DIR = Path(__file__).parent.parent.parent / "workspace" / "ledger"
HISTORY_FILE = LEDGER_DIR / "spawn-history.json"


def _now() -> datetime:
    return datetime.now()


# ── config resolution ────────────────────────────────────────────────────────

def _resolve(agent: str, task_type: str) -> tuple[dict | None, str | None]:
    """Return (merged_rule, scope_key) for the most specific matching rule, or
    (None, None) if this (agent, task_type) is not cadence-controlled.

    The scope_key is the granularity the cooldown is tracked at, so a
    by_task_type rule shares one cooldown across every agent emitting it.
    """
    sched = load_spawn_schedules()
    if not sched:
        return None, None
    defaults = sched.get("defaults", {}) or {}

    pair_rules = sched.get("by_pair", {}) or {}
    pair = f"{agent}:{task_type}"
    if pair in pair_rules:
        return {**defaults, **(pair_rules[pair] or {})}, f"pair:{pair}"

    type_rules = sched.get("by_task_type", {}) or {}
    if task_type in type_rules:
        return {**defaults, **(type_rules[task_type] or {})}, f"type:{task_type}"

    agent_rules = sched.get("by_agent", {}) or {}
    if agent in agent_rules:
        return {**defaults, **(agent_rules[agent] or {})}, f"agent:{agent}"

    return None, None


# ── persistence ──────────────────────────────────────────────────────────────

def _read() -> dict:
    if not HISTORY_FILE.exists():
        return {"last_spawn": {}, "next_allowed": {}, "counts": {}}
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"last_spawn": {}, "next_allowed": {}, "counts": {}}
    data.setdefault("last_spawn", {})
    data.setdefault("next_allowed", {})
    data.setdefault("counts", {})
    return data


def _write(data: dict) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _count_today(data: dict, key: str, now: datetime) -> int:
    return data["counts"].get(now.strftime("%Y-%m-%d"), {}).get(key, 0)


def _in_quiet_hours(quiet: dict, now: datetime) -> bool:
    if not quiet:
        return False
    start, end = quiet.get("start"), quiet.get("end")
    if start is None or end is None:
        return False
    hour = now.hour
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end  # window wraps past midnight


# ── public API ───────────────────────────────────────────────────────────────

def spawn_allowed(agent: str, task_type: str, now: datetime | None = None) -> tuple[bool, str]:
    """(allowed, reason). reason is '' when allowed, else a human-readable cause."""
    rule, key = _resolve(agent, task_type)
    if rule is None:
        return True, ""  # not cadence-controlled

    now = now or _now()

    if _in_quiet_hours(rule.get("quiet_hours") or {}, now):
        q = rule["quiet_hours"]
        return False, f"{key} is in quiet hours {q.get('start')}:00-{q.get('end')}:00"

    data = _read()

    max_per_day = rule.get("max_per_day")
    if max_per_day is not None and _count_today(data, key, now) >= max_per_day:
        return False, f"{key} hit its daily cap of {max_per_day} spawns"

    na = data["next_allowed"].get(key)
    if na:
        try:
            next_at = datetime.fromisoformat(na)
        except ValueError:
            next_at = None
        if next_at and now < next_at:
            mins = max(0, round((next_at - now).total_seconds() / 60))
            return False, f"{key} cooldown active - next spawn allowed in ~{mins} min ({na})"

    return True, ""


def record_spawn(agent: str, task_type: str, now: datetime | None = None) -> None:
    """Record an actual spawn so the cooldown + daily count advance. No-op for
    keys that are not cadence-controlled."""
    rule, key = _resolve(agent, task_type)
    if rule is None:
        return

    now = now or _now()
    interval = float(rule.get("min_interval_minutes", 0) or 0)
    jitter = float(rule.get("jitter_minutes", 0) or 0)
    effective = interval + (random.uniform(0, jitter) if jitter > 0 else 0)

    data = _read()
    data["last_spawn"][key] = now.isoformat()
    data["next_allowed"][key] = (now + timedelta(minutes=effective)).isoformat()

    today = now.strftime("%Y-%m-%d")
    counts = data["counts"].setdefault(today, {})
    counts[key] = counts.get(key, 0) + 1
    # Keep only today's counts so the file stays small.
    data["counts"] = {today: counts}

    _write(data)


def next_allowed_at(agent: str, task_type: str) -> str | None:
    """ISO timestamp when this key may next spawn, or None if uncontrolled/ready."""
    _, key = _resolve(agent, task_type)
    if key is None:
        return None
    return _read()["next_allowed"].get(key)


def describe() -> list[dict]:
    """Observability snapshot of every configured key: interval, spawns today,
    and next-allowed time. Safe to call for dashboards/reporting."""
    sched = load_spawn_schedules()
    if not sched:
        return []
    defaults = sched.get("defaults", {}) or {}
    data = _read()
    now = _now()
    rows: list[dict] = []
    sources = (
        ("pair", sched.get("by_pair", {}) or {}),
        ("type", sched.get("by_task_type", {}) or {}),
        ("agent", sched.get("by_agent", {}) or {}),
    )
    for prefix, rules in sources:
        for name, rule in rules.items():
            key = f"{prefix}:{name}"
            merged = {**defaults, **(rule or {})}
            rows.append({
                "key": key,
                "min_interval_minutes": merged.get("min_interval_minutes"),
                "max_per_day": merged.get("max_per_day"),
                "spawns_today": _count_today(data, key, now),
                "next_allowed": data["next_allowed"].get(key),
            })
    return rows
