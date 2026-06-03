import runner.main as main
from runner.tools import landing


def test_promising_row_queues_landing_build(tmp_path, monkeypatch):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    monkeypatch.setattr(main, "runway_expired", lambda: False)
    monkeypatch.setattr(main, "_opportunity_task_pending", lambda: False)
    rows = [
        {"slug": "ai-x", "composite": 80.0, "phase": "graded", "poc": "promising",
         "system_fit": "7", "est_rev_mo": "500", "status": "graded",
         "pod": "—", "updated": "2026-05-28"},
    ]
    monkeypatch.setattr("runner.tools.opportunity.read_ledger", lambda: rows)

    created = {}
    def fake_create_task(**kw):
        created.update(kw)
        return {"success": True, "task_id": "T1"}
    monkeypatch.setattr(main, "create_task", fake_create_task)

    main._advance_opportunity_pipeline()

    assert created.get("assigned_agent") == "builder"
    assert created.get("task_type") == "landing_build"
    assert "ai-x" in created.get("title", "")
    assert landing.landing_exists("ai-x") is True


def test_promising_row_with_landing_not_requeued(tmp_path, monkeypatch):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)
    landing.write_landing_state("ai-x", status="draft")
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    monkeypatch.setattr(main, "runway_expired", lambda: False)
    monkeypatch.setattr(main, "_opportunity_task_pending", lambda: False)
    monkeypatch.setattr(main, "mark_scout_ran", lambda: None, raising=False)
    rows = [
        {"slug": "ai-x", "composite": 80.0, "phase": "graded", "poc": "promising",
         "system_fit": "7", "est_rev_mo": "500", "status": "graded",
         "pod": "—", "updated": "2026-05-28"},
    ]
    monkeypatch.setattr("runner.tools.opportunity.read_ledger", lambda: rows)
    calls = []
    monkeypatch.setattr(main, "create_task", lambda **kw: calls.append(kw) or {"success": True})

    main._advance_opportunity_pipeline()

    assert not any(c.get("task_type") == "landing_build" for c in calls)
