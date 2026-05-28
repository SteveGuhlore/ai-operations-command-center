from unittest.mock import MagicMock, patch

from runner.agents.base import AgentBase

_TOOLS = [{"name": "web_research", "description": "d",
           "input_schema": {"type": "object", "properties": {}}}]


def _msg(content, tool_calls=None):
    m = MagicMock()
    m.content = content
    m.tool_calls = tool_calls
    return m


def _resp(finish_reason, message, pt=10, ct=5):
    r = MagicMock()
    r.choices = [MagicMock(finish_reason=finish_reason, message=message)]
    r.usage = MagicMock(prompt_tokens=pt, completion_tokens=ct)
    return r


def _toolcall(name, args="{}", call_id="call_1"):
    tc = MagicMock()
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = args
    return tc


def _agent(monkeypatch, create_side_effect):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("VERTEX_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    agent = AgentBase("x_worker", "moonshotai/kimi-k2.5", "sys", tools=_TOOLS)
    agent.client = MagicMock()
    agent.client.chat.completions.create.side_effect = create_side_effect
    return agent


def test_all_tools_errored_marks_hallucinated_success(monkeypatch):
    first = _resp("tool_calls", _msg("", tool_calls=[_toolcall("web_research", '{"q": "x"}')]))
    second = _resp("stop", _msg("I found and emailed 10 prospects successfully!"))
    agent = _agent(monkeypatch, [first, second])
    with patch("runner.agents.base.record_spend"), \
         patch("runner.agents.base.dispatch_tool", return_value={"error": "boom"}):
        result = agent.run({"task_id": "T1", "body": "go"})
    assert "ALL_TOOLS_ERRORED" in result["output"]


def test_all_tools_errored_marks_empty_output(monkeypatch):
    first = _resp("tool_calls", _msg("", tool_calls=[_toolcall("web_research", '{"q": "x"}')]))
    second = _resp("stop", _msg(""))
    agent = _agent(monkeypatch, [first, second])
    with patch("runner.agents.base.record_spend"), \
         patch("runner.agents.base.dispatch_tool", return_value={"error": "boom"}):
        result = agent.run({"task_id": "T2", "body": "go"})
    assert "ALL_TOOLS_ERRORED" in result["output"]


def test_partial_tool_error_not_marked(monkeypatch):
    tcs = [_toolcall("web_research", "{}", "c1"), _toolcall("file_editor", "{}", "c2")]
    first = _resp("tool_calls", _msg("", tool_calls=tcs))
    second = _resp("stop", _msg("done"))
    agent = _agent(monkeypatch, [first, second])
    results = iter([{"error": "boom"}, {"ok": True}])
    with patch("runner.agents.base.record_spend"), \
         patch("runner.agents.base.dispatch_tool", side_effect=lambda *a, **k: next(results)):
        result = agent.run({"task_id": "T3", "body": "go"})
    assert "ALL_TOOLS_ERRORED" not in result["output"]
