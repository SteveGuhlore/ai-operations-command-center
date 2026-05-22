import pytest
from unittest.mock import patch, MagicMock
from runner.tools.web import web_search, web_fetch, TOOL_SPEC


def test_web_search_returns_results():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Result 1\nResult 2")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 20
    mock_client.messages.create.return_value = mock_response

    with patch("runner.tools.web.anthropic.Anthropic", return_value=mock_client):
        result = web_search(query="python asyncio tutorial")
        assert "result" in result or "content" in result


def test_web_fetch_returns_content():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="Page content here")]
    mock_response.stop_reason = "end_turn"
    mock_response.usage.input_tokens = 10
    mock_response.usage.output_tokens = 20
    mock_client.messages.create.return_value = mock_response

    with patch("runner.tools.web.anthropic.Anthropic", return_value=mock_client):
        result = web_fetch(url="https://example.com")
        assert "content" in result or "result" in result


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "web_research"
    assert "input_schema" in TOOL_SPEC
