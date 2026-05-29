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

# Append-only audit of every gate evaluation, capped to the most recent
# MAX_DECISIONS lines so the file can't grow without bound. The path is derived
# from LEDGER_DIR at write time (not bound at import) so tests that monkeypatch
# LEDGER_DIR stay isolated in their tmp dir.
DECISIONS_NAME = "spawn-decisions.jsonl"
MAX_DECISIONS = 1000


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


# ── decision audit log (best-effort, crash-safe) ──────────────────────────────

def _log_decision(agent: str, task_type: str, key: str | None,
                  allowed: bool, reason: str, now: datetime) -> None:
    """Append one gate evaluation to spawn-decisions.jsonl, capped at the most
    recent MAX_DECISIONS lines. Observability only: any failure (permissions,
    disk, serialization) is swallowed so logging can never block a spawn."""
    try:
        entry = json.dumps({
            "ts": now.isoformat(timespec="seconds"),
            "agent": agent,
            "task_type": task_type,
            "key": key,
            "allowed": allowed,
            "reason": reason,
        })
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        path = LEDGER_DIR / DECISIONS_NAME
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        # Skip a denial identical to the previous one for this key, so a throttled
        # self-perpetuating loop (e.g. outreach every cycle) doesn't spam the feed.
        if not allowed and lines:
            try:
                prev = json.loads(lines[-1])
                if (prev.get("key") == key and prev.get("allowed") is False
                        and prev.get("reason") == reason):
                    return
            except json.JSONDecodeError:
                pass
        lines.append(entry)
        if len(lines) > MAX_DECISIONS:
            lines = lines[-MAX_DECISIONS:]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def read_decisions(limit: int | None = None) -> list[dict]:
    """Parsed decision-log entries, oldest first. Tolerates a missing file and
    skips any unparseable lines. `limit` keeps only the most recent N."""
    path = LEDGER_DIR / DECISIONS_NAME
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict] = []
    for line in raw:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:] if limit else rows


# ── public API ───────────────────────────────────────────────────────────────

def _evaluate(rule: dict | None, key: str | None, data: dict, now: datetime) -> tuple[bool, str]:
    """Pure gate decision for an already-resolved rule + persisted state."""
    if rule is None:
        return True, ""  # not cadence-controlled

    if _in_quiet_hours(rule.get("quiet_hours") or {}, now):
        q = rule["quiet_hours"]
        return False, f"{key} is in quiet hours {q.get('start')}:00-{q.get('end')}:00"

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


def spawn_allowed(agent: str, task_type: str, now: datetime | None = None) -> tuple[bool, str]:
    """(allowed, reason). reason is '' when allowed, else a human-readable cause.

    Every evaluation is appended to the decision audit log (best-effort)."""
    rule, key = _resolve(agent, task_type)
    now = now or _now()
    data = _read() if rule is not None else {"next_allowed": {}, "counts": {}}
    allowed, reason = _evaluate(rule, key, data, now)
    _log_decision(agent, task_type, key, allowed, reason, now)
    return allowed, reason


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


def describe(now=None) -> list[dict]:
    """Observability snapshot of every configured key: interval, spawns today,
    and next-allowed time. Safe to call for dashboards/reporting. `now` is
    injectable for deterministic tests; defaults to the current time."""
    sched = load_spawn_schedules()
    if not sched:
        return []
    defaults = sched.get("defaults", {}) or {}
    data = _read()
    now = now or _now()
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


# ── dashboard snapshot ─────────────────────────────────────────────────────────

def _split_key(key: str) -> tuple[str, str | None, str | None]:
    """('type:prospect_research') -> ('task_type', None, 'prospect_research')
    ('pair:outreach_worker:prospect_research') -> ('pair', agent, task_type)
    ('agent:outreach_worker') -> ('agent', 'outreach_worker', None)"""
    prefix, _, rest = key.partition(":")
    if prefix == "pair":
        agent, _, ttype = rest.partition(":")
        return "pair", agent or None, ttype or None
    if prefix == "type":
        return "task_type", None, rest or None
    if prefix == "agent":
        return "agent", rest or None, None
    return prefix or "unknown", None, rest or None


def classify_status(rule: dict | None, key: str | None, data: dict,
                    now: datetime) -> tuple[str, int | None]:
    """(status, ready_in_seconds). status is one of ready|cooldown|cap|quiet,
    classified in the same precedence the gate enforces (quiet > cap > cooldown).
    ready_in_seconds is the countdown to next-allowed when in cooldown, else None.

    A history-only key with no current rule is classified on its persisted
    next_allowed alone (cooldown vs ready)."""
    if rule and _in_quiet_hours(rule.get("quiet_hours") or {}, now):
        return "quiet", None

    if rule is not None:
        cap = rule.get("max_per_day")
        if cap is not None and _count_today(data, key, now) >= cap:
            return "cap", None

    na = data.get("next_allowed", {}).get(key)
    if na:
        try:
            next_at = datetime.fromisoformat(na)
        except ValueError:
            next_at = None
        if next_at and now < next_at:
            return "cooldown", max(0, round((next_at - now).total_seconds()))

    return "ready", None


def gate_snapshot(recent_limit: int = 20) -> dict:
    """Full observability payload for the Spawn Gate dashboard panel.

    Surfaces one row per cadence scope-key — the granularity the gate actually
    tracks cooldowns at (a by_task_type rule is one shared timer across every
    agent emitting that type, NOT one per agent) — plus any scope-key that has
    persisted history but no current config rule. Includes a summary and the
    most recent decisions for an at-a-glance audit trail."""
    sched = load_spawn_schedules() or {}
    defaults = sched.get("defaults", {}) or {}
    data = _read()
    now = _now()
    today = now.strftime("%Y-%m-%d")

    rules_by_key: dict[str, dict | None] = {}
    sources = (
        ("pair", sched.get("by_pair", {}) or {}),
        ("type", sched.get("by_task_type", {}) or {}),
        ("agent", sched.get("by_agent", {}) or {}),
    )
    for prefix, rules in sources:
        for name, rule in rules.items():
            rules_by_key[f"{prefix}:{name}"] = {**defaults, **(rule or {})}

    # Include any key seen in persisted state but no longer (or never) configured.
    history_keys = set(data.get("next_allowed", {})) | set(data.get("last_spawn", {}))
    history_keys |= set(data.get("counts", {}).get(today, {}))
    for key in history_keys:
        rules_by_key.setdefault(key, None)

    last_reason: dict[str, str] = {}
    for d in read_decisions():
        if d.get("key"):
            last_reason[d["key"]] = d.get("reason") or ("allowed" if d.get("allowed") else "")

    keys: list[dict] = []
    for key, rule in sorted(rules_by_key.items()):
        scope, agent, task_type = _split_key(key)
        status, ready_in = classify_status(rule, key, data, now)
        keys.append({
            "key": key,
            "scope": scope,
            "agent": agent,
            "task_type": task_type,
            "configured": rule is not None,
            "min_interval_minutes": (rule or {}).get("min_interval_minutes"),
            "jitter_minutes": (rule or {}).get("jitter_minutes"),
            "max_per_day": (rule or {}).get("max_per_day"),
            "quiet_hours": (rule or {}).get("quiet_hours"),
            "spawns_today": _count_today(data, key, now),
            "last_spawn": data.get("last_spawn", {}).get(key),
            "next_allowed": data.get("next_allowed", {}).get(key),
            "status": status,
            "ready_in_seconds": ready_in,
            "last_reason": last_reason.get(key),
        })

    # Sort so the things needing attention surface first: cap, quiet, cooldown, ready.
    order = {"cap": 0, "quiet": 1, "cooldown": 2, "ready": 3}
    keys.sort(key=lambda r: (order.get(r["status"], 9), r["key"]))

    recent = read_decisions(limit=recent_limit)
    denials_today = sum(
        1 for d in read_decisions()
        if d.get("allowed") is False and (d.get("ts") or "").startswith(today)
    )
    spawns_today = sum((data.get("counts", {}).get(today, {}) or {}).values())

    return {
        "now": now.isoformat(timespec="seconds"),
        "summary": {
            "spawns_today": spawns_today,
            "denials_today": denials_today,
            "in_cooldown": sum(1 for k in keys if k["status"] == "cooldown"),
            "at_cap": sum(1 for k in keys if k["status"] == "cap"),
            "ready": sum(1 for k in keys if k["status"] == "ready"),
            "tracked_keys": len(keys),
        },
        "keys": keys,
        "recent": list(reversed(recent)),  # newest first for the activity feed
    }
