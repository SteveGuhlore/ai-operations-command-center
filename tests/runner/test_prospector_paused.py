import runner.main as main


def test_paused_pipeline_spawns_nothing(monkeypatch):
    monkeypatch.setattr(main, "PROSPECTOR_PAUSED", True)
    calls = []
    monkeypatch.setattr(main, "create_task", lambda **kw: calls.append(kw) or {"success": True})
    # Anything past the gate would need these; if the gate works they're never reached.
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    monkeypatch.setattr(main, "runway_expired", lambda: False)

    main._advance_opportunity_pipeline()

    assert calls == []  # gate returned early — no scout/deep-dive/poc spawned


def test_unpaused_pipeline_spawns_scout(monkeypatch):
    monkeypatch.setattr(main, "PROSPECTOR_PAUSED", False)
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    monkeypatch.setattr(main, "runway_expired", lambda: False)
    monkeypatch.setattr(main, "_opportunity_task_pending", lambda: False)
    monkeypatch.setattr("runner.tools.opportunity.read_ledger", lambda: [])  # empty -> fresh scout
    monkeypatch.setattr(main, "mark_scout_ran", lambda: None, raising=False)
    calls = []
    monkeypatch.setattr(main, "create_task", lambda **kw: calls.append(kw) or {"success": True})

    main._advance_opportunity_pipeline()

    assert any(c.get("task_type") == "opportunity_scout" for c in calls)


def test_run_task_clears_queued_opportunity_task_when_paused(monkeypatch):
    monkeypatch.setattr(main, "PROSPECTOR_PAUSED", True)
    monkeypatch.setattr(main, "route_task", lambda t: "opportunity_worker")
    monkeypatch.setattr(main, "acquire_lock", lambda tid, rid: True)
    monkeypatch.setattr(main, "is_budget_exceeded", lambda *a, **k: False)

    moves, outputs, released = [], [], []
    monkeypatch.setattr(main, "move_task", lambda tid, src, dst: moves.append((tid, src, dst)))
    monkeypatch.setattr(main, "write_task_output", lambda tid, text, status: outputs.append((tid, status)))
    monkeypatch.setattr(main, "release_lock", lambda tid: released.append(tid))

    def _no_agent(*a, **k):
        raise AssertionError("AgentBase must not run for a paused opportunity_pod task")
    monkeypatch.setattr(main, "AgentBase", _no_agent)

    result = main.run_task({"task_id": "OPP-1", "pod": "opportunity_pod", "body": "x"})

    assert ("OPP-1", "todo", "failed") in moves   # cleared once, not skip-retried
    assert ("OPP-1", "failed") in outputs          # reason recorded in task output
    assert "OPP-1" in released
    assert result.get("reason") == "prospector paused"
