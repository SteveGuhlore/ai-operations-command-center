# tests/runner/test_budget_pods.py
import importlib


def _fresh_budget(tmp_path, monkeypatch):
    import runner.ledger.budget as budget

    importlib.reload(budget)
    monkeypatch.setattr(budget, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(budget, "SPEND_FILE", tmp_path / "daily-spend.json")
    return budget


def test_record_spend_tracks_pod(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    budget.record_spend("opportunity_worker", 1.5, pod="opportunity_pod")
    budget.record_spend("heavy_worker", 0.5, pod="opportunity_pod")
    assert budget.get_pod_spend("opportunity_pod") == 2.0


def test_record_spend_without_pod_is_safe(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    budget.record_spend("outreach_worker", 0.25)
    assert budget.get_pod_spend("opportunity_pod") == 0.0
    assert budget.get_daily_spend() == 0.25


def test_pod_budget_exceeded(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    monkeypatch.setattr(budget, "get_pod_cap", lambda pod: 10.0)
    budget.record_spend("opportunity_worker", 9.99, pod="opportunity_pod")
    assert budget.is_pod_budget_exceeded("opportunity_pod") is False
    budget.record_spend("opportunity_worker", 0.02, pod="opportunity_pod")
    assert budget.is_pod_budget_exceeded("opportunity_pod") is True


def test_agentbase_passes_pod(monkeypatch):
    import runner.agents.base as base

    # AgentBase builds an OpenAI-compatible client at construction; pin routing to
    # OpenRouter with a dummy key so the test is hermetic (no real key / network).
    for var in ("VERTEX_PROJECT", "GOOGLE_CLOUD_PROJECT", "GOOGLE_AI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    calls = []
    monkeypatch.setattr(
        base, "record_spend", lambda role, cost, pod=None: calls.append((role, pod))
    )
    monkeypatch.setattr(base, "dispatch_tool", lambda *a, **k: {})

    agent = base.AgentBase("opportunity_worker", "gemini-2.5-flash", "sys", tools=[])

    class _Msg:
        content = "done"
        tool_calls = None

    class _Choice:
        finish_reason = "stop"
        message = _Msg()

    class _Usage:
        prompt_tokens = 10
        completion_tokens = 5

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    monkeypatch.setattr(agent.client.chat.completions, "create", lambda **k: _Resp())

    agent.run({"task_id": "T1", "body": "hi", "pod": "opportunity_pod"})
    assert calls and calls[0][1] == "opportunity_pod"


def test_run_task_skips_when_pod_budget_exceeded(monkeypatch):
    import runner.main as main

    monkeypatch.setattr(
        main, "PROSPECTOR_PAUSED", False
    )  # reach the budget-skip path under test
    monkeypatch.setattr(main, "route_task", lambda t: "opportunity_worker")
    monkeypatch.setattr(main, "acquire_lock", lambda *a: True)
    monkeypatch.setattr(main, "release_lock", lambda *a: None)
    monkeypatch.setattr(
        main, "is_budget_exceeded", lambda **k: False
    )  # run_task passes off_hours=
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: True)
    called = {"ran": False}

    def _should_not_run(*a, **k):
        called["ran"] = True

    monkeypatch.setattr(main, "move_task", _should_not_run)

    result = main.run_task({"task_id": "T1", "pod": "opportunity_pod"})
    assert result.get("skipped") is True
    assert called["ran"] is False
