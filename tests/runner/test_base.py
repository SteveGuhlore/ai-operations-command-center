import pytest
from unittest.mock import MagicMock, patch
from runner.agents.base import AgentBase, calculate_cost


def test_calculate_cost_opus():
    cost = calculate_cost("claude-opus-4-7", 1_000_000, 1_000_000)
    assert cost == pytest.approx(90.0)  # (15 + 75) per million


def test_calculate_cost_sonnet():
    cost = calculate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0)  # (3 + 15) per million


def test_calculate_cost_haiku():
    cost = calculate_cost("claude-haiku-4-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(4.8)  # (0.8 + 4.0) per million


def test_agent_run_returns_output(monkeypatch):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Task completed successfully.")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50

    with patch("runner.agents.base.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        with patch("runner.agents.base.record_spend"):
            agent = AgentBase("debug_worker", "claude-haiku-4-5", "You are Scout.")
            task = {"task_id": "TEST-001", "body": "Check environment."}
            result = agent.run(task)

    assert result["output"] == "Task completed successfully."
    assert result["task_id"] == "TEST-001"
    assert result["role_id"] == "debug_worker"
    assert result["cost_usd"] > 0
