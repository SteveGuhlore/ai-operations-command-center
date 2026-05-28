"""Tests for the Spawn Gate observability layer: decision logging, status
classification, the gate_snapshot payload, and the /api/spawn-gate endpoint."""
import asyncio
import importlib
import json
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
    "by_task_type": {"prospect_research": {"min_interval_minutes": 30, "max_per_day": 40}},
    "by_agent": {},
    "by_pair": {},
}


# ── decision logging ────────────────────────────────────────────────────────

def test_spawn_allowed_appends_a_decision(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    sg.spawn_allowed("outreach_worker", "prospect_research", now=datetime(2026, 5, 28, 12, 0))
    decisions = sg.read_decisions()
    assert len(decisions) == 1
    d = decisions[0]
    assert d["agent"] == "outreach_worker"
    assert d["key"] == "type:prospect_research"
    assert d["allowed"] is True
    assert "ts" in d and "reason" in d


def test_logger_crash_safe_on_unwritable_ledger(tmp_path, monkeypatch):
    # Point LEDGER_DIR at an existing *file* so mkdir() raises — the gate must
    # still return a normal decision and not propagate the error.
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    sg = _fresh(tmp_path, monkeypatch, {})  # no rules -> always allowed path
    monkeypatch.setattr(sg, "LEDGER_DIR", blocker)
    result = sg.spawn_allowed("outreach_worker", "prospect_research", now=datetime(2026, 5, 28, 12, 0))
    assert result == (True, "")
    assert blocker.is_file()  # untouched, no crash


def test_log_rotation_caps_at_limit(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    monkeypatch.setattr(sg, "MAX_DECISIONS", 5)
    for i in range(12):
        sg.spawn_allowed("outreach_worker", "prospect_research", now=datetime(2026, 5, 28, 12, i))
    decisions = sg.read_decisions()
    assert len(decisions) == 5
    # the kept entries are the most recent ones
    assert decisions[-1]["ts"].endswith("12:11:00")
    raw = (tmp_path / "spawn-decisions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(raw) == 5


def test_read_decisions_skips_corrupt_lines(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    (tmp_path / "spawn-decisions.jsonl").write_text(
        '{"ts":"2026-05-28T12:00:00","allowed":true}\nNOT JSON\n{"ts":"x","allowed":false}\n',
        encoding="utf-8",
    )
    rows = sg.read_decisions()
    assert len(rows) == 2  # the junk line is skipped, not fatal


# ── status classification ───────────────────────────────────────────────────

def test_classify_ready(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    rule = {"min_interval_minutes": 30, "max_per_day": 40}
    data = {"next_allowed": {}, "counts": {}}
    status, secs = sg.classify_status(rule, "type:x", data, datetime(2026, 5, 28, 12, 0))
    assert status == "ready" and secs is None


def test_classify_cooldown_reports_seconds(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    now = datetime(2026, 5, 28, 12, 0)
    data = {"next_allowed": {"type:x": (now + timedelta(minutes=10)).isoformat()}, "counts": {}}
    status, secs = sg.classify_status({"min_interval_minutes": 30}, "type:x", data, now)
    assert status == "cooldown"
    assert 590 <= secs <= 600


def test_classify_cap(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    now = datetime(2026, 5, 28, 12, 0)
    today = now.strftime("%Y-%m-%d")
    data = {"next_allowed": {}, "counts": {today: {"type:x": 40}}}
    status, secs = sg.classify_status({"max_per_day": 40}, "type:x", data, now)
    assert status == "cap" and secs is None


def test_classify_quiet_takes_precedence_over_cooldown(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    now = datetime(2026, 5, 28, 3, 0)  # inside 1-6 quiet window
    rule = {"quiet_hours": {"start": 1, "end": 6}, "max_per_day": 40}
    data = {"next_allowed": {"type:x": (now + timedelta(minutes=10)).isoformat()},
            "counts": {now.strftime("%Y-%m-%d"): {"type:x": 40}}}
    status, _ = sg.classify_status(rule, "type:x", data, now)
    assert status == "quiet"


def test_classify_history_only_key_without_rule(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    now = datetime(2026, 5, 28, 12, 0)
    data = {"next_allowed": {"type:gone": (now + timedelta(minutes=5)).isoformat()}, "counts": {}}
    status, secs = sg.classify_status(None, "type:gone", data, now)
    assert status == "cooldown" and secs > 0


# ── gate_snapshot payload ───────────────────────────────────────────────────

def test_gate_snapshot_shape_with_seeded_state(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    (tmp_path / "spawn-history.json").write_text(json.dumps({
        "last_spawn": {"type:prospect_research": now.isoformat()},
        "next_allowed": {"type:prospect_research": (now + timedelta(minutes=20)).isoformat()},
        "counts": {today: {"type:prospect_research": 3}},
    }), encoding="utf-8")

    snap = sg.gate_snapshot()
    assert set(snap) == {"now", "summary", "keys", "recent"}
    assert snap["summary"]["spawns_today"] == 3
    assert snap["summary"]["tracked_keys"] >= 1

    row = next(r for r in snap["keys"] if r["key"] == "type:prospect_research")
    assert row["scope"] == "task_type"
    assert row["task_type"] == "prospect_research"
    assert row["configured"] is True
    assert row["min_interval_minutes"] == 30
    assert row["max_per_day"] == 40
    assert row["spawns_today"] == 3
    assert row["status"] == "cooldown"
    assert row["ready_in_seconds"] > 0
    assert row["next_allowed"]


def test_gate_snapshot_includes_history_only_keys(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    now = datetime.now()
    (tmp_path / "spawn-history.json").write_text(json.dumps({
        "last_spawn": {}, "counts": {},
        "next_allowed": {"agent:retired_worker": (now + timedelta(minutes=5)).isoformat()},
    }), encoding="utf-8")
    snap = sg.gate_snapshot()
    row = next(r for r in snap["keys"] if r["key"] == "agent:retired_worker")
    assert row["configured"] is False
    assert row["scope"] == "agent"
    assert row["agent"] == "retired_worker"


def test_gate_snapshot_counts_denials_today(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    today = datetime.now().strftime("%Y-%m-%d")
    (tmp_path / "spawn-decisions.jsonl").write_text(
        f'{{"ts":"{today}T11:00:00","key":"type:prospect_research","allowed":false,"reason":"cooldown"}}\n'
        f'{{"ts":"{today}T11:30:00","key":"type:prospect_research","allowed":true,"reason":""}}\n'
        f'{{"ts":"2020-01-01T00:00:00","key":"type:prospect_research","allowed":false,"reason":"old"}}\n',
        encoding="utf-8",
    )
    snap = sg.gate_snapshot()
    assert snap["summary"]["denials_today"] == 1  # only today's denial counts
    assert len(snap["recent"]) == 3
    assert snap["recent"][0]["ts"] == "2020-01-01T00:00:00"  # newest-first: last line first


# ── endpoint ────────────────────────────────────────────────────────────────

def test_api_spawn_gate_endpoint_shape(tmp_path, monkeypatch):
    sg = _fresh(tmp_path, monkeypatch, _BASE)
    now = datetime.now()
    (tmp_path / "spawn-history.json").write_text(json.dumps({
        "last_spawn": {}, "next_allowed": {},
        "counts": {now.strftime("%Y-%m-%d"): {"type:prospect_research": 1}},
    }), encoding="utf-8")

    import dashboard.server as server
    result = asyncio.run(server.api_spawn_gate())
    assert set(result) == {"now", "summary", "keys", "recent"}
    assert result["summary"]["spawns_today"] == 1
    assert any(r["key"] == "type:prospect_research" for r in result["keys"])
