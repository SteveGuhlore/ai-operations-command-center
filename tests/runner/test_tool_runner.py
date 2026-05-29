import pytest
from unittest.mock import MagicMock, patch
from runner.agents.tool_runner import dispatch_tool, TOOL_REGISTRY


def test_dispatch_tool_calls_registered_adapter():
    mock_adapter = MagicMock(return_value={"result": "ok"})
    with patch.dict(TOOL_REGISTRY, {"test_tool": mock_adapter}):
        result = dispatch_tool("test_tool", {"arg": "value"})
        mock_adapter.assert_called_once_with(arg="value")
        assert result == {"result": "ok"}


def test_dispatch_tool_raises_on_unknown_tool():
    with pytest.raises(ValueError, match="Unknown tool"):
        dispatch_tool("nonexistent_tool_xyz", {})


def test_dispatch_tool_returns_error_string_on_adapter_exception():
    def bad_adapter(**kwargs):
        raise RuntimeError("adapter failed")
    with patch.dict(TOOL_REGISTRY, {"bad_tool": bad_adapter}):
        result = dispatch_tool("bad_tool", {})
        assert "error" in str(result).lower()


from runner.agents.base import AgentBase


def _tool_call_response(tool_name, arguments_json, call_id="tu_001"):
    """OpenAI-shaped response that requests one tool call."""
    fn = MagicMock()
    fn.name = tool_name
    fn.arguments = arguments_json
    tc = MagicMock()
    tc.id = call_id
    tc.function = fn
    msg = MagicMock()
    msg.content = ""
    msg.tool_calls = [tc]
    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.prompt_tokens = 50
    resp.usage.completion_tokens = 20
    return resp


def _final_response(text="Task complete."):
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.prompt_tokens = 60
    resp.usage.completion_tokens = 30
    return resp


def test_agent_executes_tool_use_loop():
    mock_tool = MagicMock(return_value={"content": "file contents here"})
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _tool_call_response("read_file", '{"path": "README.md"}'),
        _final_response("Task complete."),
    ]

    tools_spec = [{
        "name": "read_file",
        "description": "Read a file",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }]

    with patch("runner.agents.base.openai.OpenAI", return_value=mock_client), \
         patch("runner.agents.base.record_spend"), \
         patch.dict("runner.agents.tool_runner.TOOL_REGISTRY", {"read_file": mock_tool}):
        agent = AgentBase("debug_worker", "claude-haiku-4-5", "You are Scout.", tools=tools_spec)
        result = agent.run({"task_id": "T-001", "body": "Read README."})

    assert result["output"] == "Task complete."
    assert mock_client.chat.completions.create.call_count == 2
    mock_tool.assert_called_once_with(path="README.md")
