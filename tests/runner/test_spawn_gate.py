import importlib
from datetime import datetime, timedelta


def _fresh(tmp_path, monkeypatch, schedules):
    import runner.scheduler.spawn_gate as sg
    importlib.reload(sg)
    monkeypatch.setattr(sg, "HISTORY_FILE", tmp_path / "spawn-history.json")
    monkeypatch.setattr(sg, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(sg, "load_spawn_schedules", lambda: schedules)
    return sg


_BASE = {
    "defaults": {"min_interval_minutes": 30, "jitter_minutes": 0},
    "by_task_type": {"prospect_research": {"min_interval_minutes": 30}},
    "by_agent": {},
    "by_pair": {},
}


# ── resolution ────────────────────────────────────────────────────────────────

def test_unmatched_key_is_always_allowed(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    allowed, reason = sg.spawn_allowed("builder", "site_build")
    assert allowed is True
    assert reason == ""


def test_no_config_means_no_enforcement(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, {})
    assert sg.spawn_allowed("outreach_worker", "prospect_research")[0] is True


def test_resolution_precedence_pair_beats_type_beats_agent(tmp_path, monkeypatch):
    sched = {
        "defaults": {"min_interval_minutes": 5},
        "by_agent": {"outreach_worker": {"min_interval_minutes": 10}},
        "by_task_type": {"prospect_research": {"min_interval_minutes": 20}},
        "by_pair": {"outreach_worker:prospect_research": {"min_interval_minutes": 40}},
    }
    sg = _fresh(tmp_path, monkeypatch, sched)
    rule, key = sg._resolve("outreach_worker", "prospect_research")
    assert key == "pair:outreach_worker:prospect_research"
    assert rule["min_interval_minutes"] == 40

    # drop the pair -> type wins
    del sched["by_pair"]["outreach_worker:prospect_research"]
    rule, key = sg._resolve("outreach_worker", "prospect_research")
    assert key == "type:prospect_research"
    assert rule["min_interval_minutes"] == 20

    # a different agent, same type still matches by_task_type
    rule, key = sg._resolve("debug_worker", "prospect_research")
    assert key == "type:prospect_research"


def test_defaults_inherited_when_rule_omits_knob(tmp_path, monkeypatch):
    sched = {
        "defaults": {"min_interval_minutes": 30, "jitter_minutes": 2},
        "by_agent": {"some_worker": {}},  # empty rule -> inherits everything
        "by_task_type": {},
        "by_pair": {},
    }
    sg = _fresh(tmp_path, monkeypatch, sched)
    rule, key = sg._resolve("some_worker", "anything")
    assert key == "agent:some_worker"
    assert rule["min_interval_minutes"] == 30


# ── cooldown ────────────────────────────────────────────────────────────────

def test_cooldown_blocks_then_allows(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    t0 = datetime(2026, 5, 28, 12, 0, 0)
    assert sg.spawn_allowed("outreach_worker", "prospect_research", now=t0)[0] is True

    sg.record_spawn("outreach_worker", "prospect_research", now=t0)

    # 10 min later: still blocked
    blocked, reason = sg.spawn_allowed("outreach_worker", "prospect_research", now=t0 + timedelta(minutes=10))
    assert blocked is False
    assert "cooldown" in reason

    # 31 min later: allowed again
    assert sg.spawn_allowed("outreach_worker", "prospect_research", now=t0 + timedelta(minutes=31))[0] is True


def test_shared_cooldown_across_agents_for_same_task_type(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    t0 = datetime(2026, 5, 28, 12, 0, 0)
    sg.record_spawn("outreach_worker", "prospect_research", now=t0)
    # different agent, same type, shares the type-scoped cooldown
    blocked, _ = sg.spawn_allowed("debug_worker", "prospect_research", now=t0 + timedelta(minutes=5))
    assert blocked is False


# ── daily cap ─────────────────────────────────────────────────────────────────

def test_daily_cap_blocks_after_limit(tmp_path, monkeypatch):
    sched = {
        "defaults": {"min_interval_minutes": 0},
        "by_task_type": {"prospect_research": {"min_interval_minutes": 0, "max_per_day": 2}},
        "by_agent": {}, "by_pair": {},
    }
    sg = _fresh(tmp_path, monkeypatch, sched)
    t0 = datetime(2026, 5, 28, 9, 0, 0)
    sg.record_spawn("outreach_worker", "prospect_research", now=t0)
    sg.record_spawn("outreach_worker", "prospect_research", now=t0 + timedelta(minutes=1))
    blocked, reason = sg.spawn_allowed("outreach_worker", "prospect_research", now=t0 + timedelta(minutes=2))
    assert blocked is False
    assert "daily cap" in reason


# ── quiet hours ───────────────────────────────────────────────────────────────

def test_quiet_hours_simple_window(tmp_path, monkeypatch):
    sched = {
        "defaults": {"min_interval_minutes": 0},
        "by_task_type": {"x": {"quiet_hours": {"start": 1, "end": 6}}},
        "by_agent": {}, "by_pair": {},
    }
    sg = _fresh(tmp_path, monkeypatch, sched)
    assert sg.spawn_allowed("w", "x", now=datetime(2026, 5, 28, 3, 0))[0] is False
    assert sg.spawn_allowed("w", "x", now=datetime(2026, 5, 28, 8, 0))[0] is True


def test_quiet_hours_wraps_midnight(tmp_path, monkeypatch):
    sched = {
        "defaults": {"min_interval_minutes": 0},
        "by_task_type": {"x": {"quiet_hours": {"start": 22, "end": 6}}},
        "by_agent": {}, "by_pair": {},
    }
    sg = _fresh(tmp_path, monkeypatch, sched)
    assert sg.spawn_allowed("w", "x", now=datetime(2026, 5, 28, 23, 0))[0] is False  # after start
    assert sg.spawn_allowed("w", "x", now=datetime(2026, 5, 28, 3, 0))[0] is False   # before end
    assert sg.spawn_allowed("w", "x", now=datetime(2026, 5, 28, 12, 0))[0] is True   # midday


# ── persistence ───────────────────────────────────────────────────────────────

def test_cooldown_survives_reload(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    t0 = datetime(2026, 5, 28, 12, 0, 0)
    sg.record_spawn("outreach_worker", "prospect_research", now=t0)
    assert (tmp_path / "spawn-history.json").exists()

    # simulate a restart: reload module, re-point at same history file
    sg2 = _fresh(tmp_path, monkeypatch, _BASE)
    blocked, _ = sg2.spawn_allowed("outreach_worker", "prospect_research", now=t0 + timedelta(minutes=5))
    assert blocked is False


def test_record_spawn_noop_for_unmatched_key(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    sg.record_spawn("builder", "site_build", now=datetime(2026, 5, 28, 12, 0))
    assert not (tmp_path / "spawn-history.json").exists()


def test_jitter_extends_but_respects_minimum(tmp_path, monkeypatch):
    sched = {
        "defaults": {"min_interval_minutes": 30, "jitter_minutes": 10},
        "by_task_type": {"prospect_research": {}},
        "by_agent": {}, "by_pair": {},
    }
    sg = _fresh(tmp_path, monkeypatch, sched)
    t0 = datetime(2026, 5, 28, 12, 0, 0)
    sg.record_spawn("outreach_worker", "prospect_research", now=t0)
    na = datetime.fromisoformat(sg.next_allowed_at("outreach_worker", "prospect_research"))
    delta_min = (na - t0).total_seconds() / 60
    assert 30 <= delta_min <= 40


def test_describe_reports_configured_keys(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    t0 = datetime(2026, 5, 28, 12, 0)
    sg.record_spawn("outreach_worker", "prospect_research", now=t0)
    rows = sg.describe(now=t0 + timedelta(minutes=5))
    keys = {r["key"] for r in rows}
    assert "type:prospect_research" in keys
    row = next(r for r in rows if r["key"] == "type:prospect_research")
    assert row["spawns_today"] == 1
    assert row["min_interval_minutes"] == 30


# ── create_task integration ───────────────────────────────────────────────────

def test_create_task_blocked_by_cooldown(tmp_path, monkeypatch):
    import runner.scheduler.spawn_gate as sg
    importlib.reload(sg)
    monkeypatch.setattr(sg, "HISTORY_FILE", tmp_path / "spawn-history.json")
    monkeypatch.setattr(sg, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(sg, "load_spawn_schedules", lambda: _BASE)

    import runner.tools.task_creator as tc
    importlib.reload(tc)
    monkeypatch.setattr(tc, "TASKS_DIR", tmp_path / "tasks")
    # rebind the gate functions tc imported to our freshly-patched module
    monkeypatch.setattr(tc, "spawn_allowed", sg.spawn_allowed)
    monkeypatch.setattr(tc, "record_spawn", sg.record_spawn)

    first = tc.create_task(
        title="Pitch run", body="b", assigned_agent="outreach_worker", task_type="prospect_research",
    )
    assert first.get("success") is True

    # simulate the task being picked up (leaves todo) so dedup does not mask the cooldown
    created = tmp_path / "tasks" / "todo"
    for f in created.glob("*.md"):
        f.unlink()

    second = tc.create_task(
        title="Pitch run", body="b", assigned_agent="outreach_worker", task_type="prospect_research",
    )
    assert second.get("skipped") is True
    assert "cooldown" in second.get("reason", "")


def test_create_task_unlisted_type_not_throttled(tmp_path, monkeypatch):
    import runner.scheduler.spawn_gate as sg
    importlib.reload(sg)
    monkeypatch.setattr(sg, "HISTORY_FILE", tmp_path / "spawn-history.json")
    monkeypatch.setattr(sg, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(sg, "load_spawn_schedules", lambda: _BASE)

    import runner.tools.task_creator as tc
    importlib.reload(tc)
    monkeypatch.setattr(tc, "TASKS_DIR", tmp_path / "tasks")
    monkeypatch.setattr(tc, "spawn_allowed", sg.spawn_allowed)
    monkeypatch.setattr(tc, "record_spawn", sg.record_spawn)

    r1 = tc.create_task(title="Build A", body="b", assigned_agent="builder", task_type="site_build")
    for f in (tmp_path / "tasks" / "todo").glob("*.md"):
        f.unlink()
    r2 = tc.create_task(title="Build B", body="b", assigned_agent="builder", task_type="site_build")
    assert r1.get("success") is True
    assert r2.get("success") is True
