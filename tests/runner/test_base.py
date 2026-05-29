import pytest
from unittest.mock import MagicMock, patch
from runner.agents.base import AgentBase, calculate_cost


def test_calculate_cost_opus():
    cost = calculate_cost("claude-opus-4-8", 1_000_000, 1_000_000)
    assert cost == pytest.approx(90.0)  # (15 + 75) per million


def test_calculate_cost_sonnet():
    cost = calculate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0)  # (3 + 15) per million


def test_calculate_cost_haiku():
    cost = calculate_cost("claude-haiku-4-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(4.8)  # (0.8 + 4.0) per million


def _openai_response(text):
    """Build an OpenAI-shaped chat.completions response (the client base.py uses)."""
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    return resp


def test_agent_run_returns_output():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _openai_response("Task completed successfully.")

    with patch("runner.agents.base.openai.OpenAI", return_value=mock_client), \
         patch("runner.agents.base.record_spend"):
        agent = AgentBase("debug_worker", "claude-haiku-4-5", "You are Scout.")
        result = agent.run({"task_id": "TEST-001", "body": "Check environment."})

    assert result["output"] == "Task completed successfully."
    assert result["task_id"] == "TEST-001"
    assert result["role_id"] == "debug_worker"
    assert result["cost_usd"] > 0
