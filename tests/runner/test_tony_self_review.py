import runner.main as main


def test_self_review_spawns_when_due_and_graded(monkeypatch):
    monkeypatch.setattr(main, "tony_self_review_due", lambda: True)
    monkeypatch.setattr(main, "mark_tony_self_review_ran", lambda: None)
    monkeypatch.setattr("runner.ledger.tony_scorecard.compute_record",
                        lambda: {"status": "scored", "graded": 5})
    created = {}
    monkeypatch.setattr(main, "create_task", lambda **k: created.update(k) or {"success": True})
    main._maybe_run_tony_self_review()
    assert created.get("task_type") == "tony_self_review"
    assert created.get("assigned_agent") == "market_research_worker"


def test_no_review_when_not_due(monkeypatch):
    monkeypatch.setattr(main, "tony_self_review_due", lambda: False)
    created = {}
    monkeypatch.setattr(main, "create_task", lambda **k: created.update(k) or {"success": True})
    main._maybe_run_tony_self_review()
    assert created == {}


def test_no_review_when_awaiting_outcomes(monkeypatch):
    monkeypatch.setattr(main, "tony_self_review_due", lambda: True)
    monkeypatch.setattr("runner.ledger.tony_scorecard.compute_record",
                        lambda: {"status": "awaiting_outcomes", "graded": 0})
    created = {}
    monkeypatch.setattr(main, "create_task", lambda **k: created.update(k) or {"success": True})
    main._maybe_run_tony_self_review()
    assert created == {}
