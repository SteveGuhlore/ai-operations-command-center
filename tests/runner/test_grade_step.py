import runner.main as main
from runner.tools import landing


def _setup(monkeypatch, tmp_path, built_slugs):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    monkeypatch.setattr(main, "_opportunity_task_pending", lambda: False)
    monkeypatch.setattr(main, "_poc_built", lambda slug: slug in built_slugs)


def _rows(**over):
    base = {"slug": "ai-x", "composite": 80.0, "phase": "deepdived", "poc": "—",
            "system_fit": "7", "est_rev_mo": "500", "status": "deepdived",
            "pod": "—", "updated": "2026-05-28"}
    base.update(over)
    return [base]


def test_built_ungraded_poc_queues_grade_task(tmp_path, monkeypatch):
    _setup(monkeypatch, tmp_path, built_slugs={"ai-x"})
    monkeypatch.setattr("runner.tools.opportunity.read_ledger", lambda: _rows())
    created = {}
    monkeypatch.setattr(main, "create_task", lambda **kw: created.update(kw) or {"success": True})
    main._advance_opportunity_pipeline()
    assert created.get("task_type") == "poc_grade"
    assert created.get("assigned_agent") == "opportunity_worker"
    assert "ai-x" in created.get("title", "")


def test_unbuilt_deepdived_poc_queues_build_not_grade(tmp_path, monkeypatch):
    _setup(monkeypatch, tmp_path, built_slugs=set())
    monkeypatch.setattr("runner.tools.opportunity.read_ledger", lambda: _rows())
    created = {}
    monkeypatch.setattr(main, "create_task", lambda **kw: created.update(kw) or {"success": True})
    main._advance_opportunity_pipeline()
    assert created.get("task_type") == "poc_build"
