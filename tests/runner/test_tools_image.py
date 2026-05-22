import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from runner.tools.image import generate_image, TOOL_SPEC


def test_generate_image_saves_file(tmp_path):
    mock_client = MagicMock()
    mock_image = MagicMock()
    mock_image.b64_json = "aGVsbG8="  # base64 "hello"
    mock_client.images.generate.return_value = MagicMock(data=[mock_image])

    with patch("runner.tools.image.openai.OpenAI", return_value=mock_client):
        with patch("runner.tools.image.OUTPUT_DIR", tmp_path):
            result = generate_image(prompt="a red circle", filename="test_image.png")
            assert result["success"] is True
            assert (tmp_path / "test_image.png").exists()


def test_generate_image_returns_error_on_api_failure():
    with patch("runner.tools.image.openai.OpenAI") as mock_cls:
        mock_cls.return_value.images.generate.side_effect = Exception("API error")
        result = generate_image(prompt="test", filename="out.png")
        assert "error" in result


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "image_generation"
    assert "input_schema" in TOOL_SPEC
