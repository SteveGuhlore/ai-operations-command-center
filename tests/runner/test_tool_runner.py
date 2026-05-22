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


from unittest.mock import patch, MagicMock
from runner.agents.base import AgentBase


def _make_tool_response(tool_name, tool_input, tool_use_id="tu_001"):
    tool_use = MagicMock()
    tool_use.type = "tool_use"
    tool_use.id = tool_use_id
    tool_use.name = tool_name
    tool_use.input = tool_input

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_use]
    response.usage.input_tokens = 50
    response.usage.output_tokens = 20
    return response


def _make_final_response(text="Done."):
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = text

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [text_block]
    response.usage.input_tokens = 60
    response.usage.output_tokens = 30
    return response


def test_agent_executes_tool_use_loop():
    mock_tool = MagicMock(return_value={"content": "file contents here"})

    with patch("runner.agents.base.anthropic.Anthropic") as mock_anthropic_cls:
        with patch("runner.agents.base.record_spend"):
            with patch.dict("runner.agents.tool_runner.TOOL_REGISTRY", {"read_file": mock_tool}):
                mock_client = MagicMock()
                mock_anthropic_cls.return_value = mock_client
                mock_client.messages.create.side_effect = [
                    _make_tool_response("read_file", {"path": "README.md"}),
                    _make_final_response("Task complete."),
                ]

                tools_spec = [{
                    "name": "read_file",
                    "description": "Read a file",
                    "input_schema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    }
                }]

                agent = AgentBase(
                    "debug_worker", "claude-haiku-4-5", "You are Scout.",
                    tools=tools_spec
                )
                result = agent.run({"task_id": "T-001", "body": "Read README."})

                assert result["output"] == "Task complete."
                assert mock_client.messages.create.call_count == 2
                mock_tool.assert_called_once_with(path="README.md")
