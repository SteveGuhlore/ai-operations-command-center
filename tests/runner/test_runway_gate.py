import runner.main as main


def test_runway_expired_pauses_and_skips_all_work(monkeypatch):
    monkeypatch.setattr(main, "PROSPECTOR_PAUSED", False)
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    monkeypatch.setattr(main, "_opportunity_task_pending", lambda: False)
    monkeypatch.setattr(main, "runway_expired", lambda: True)
    paused = {}
    monkeypatch.setattr(main, "pause_pod", lambda: paused.update(done=True) or {})
    calls = []
    monkeypatch.setattr(main, "create_task", lambda **kw: calls.append(kw) or {"success": True})

    main._advance_opportunity_pipeline()

    assert paused.get("done") is True       # plug pulled
    assert calls == []                      # no new work spawned


def test_runway_alive_does_not_pause(monkeypatch):
    monkeypatch.setattr(main, "PROSPECTOR_PAUSED", False)
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    monkeypatch.setattr(main, "_opportunity_task_pending", lambda: True)  # short-circuit after gate
    monkeypatch.setattr(main, "runway_expired", lambda: False)
    paused = {}
    monkeypatch.setattr(main, "pause_pod", lambda: paused.update(done=True) or {})

    main._advance_opportunity_pipeline()

    assert paused.get("done") is None       # alive → never paused
