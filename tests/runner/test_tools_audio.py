import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from runner.tools.audio import generate_audio, TOOL_SPEC


def test_generate_audio_saves_file(tmp_path):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = b"fake_audio_bytes"
    mock_client.audio.speech.create.return_value = mock_response

    with patch("runner.tools.audio.openai.OpenAI", return_value=mock_client):
        with patch("runner.tools.audio.OUTPUT_DIR", tmp_path):
            result = generate_audio(text="Hello world", filename="intro.mp3")
            assert result["success"] is True
            assert (tmp_path / "intro.mp3").exists()


def test_generate_audio_returns_error_on_failure():
    with patch("runner.tools.audio.openai.OpenAI") as mock_cls:
        mock_cls.return_value.audio.speech.create.side_effect = Exception("TTS error")
        result = generate_audio(text="test", filename="out.mp3")
        assert "error" in result


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "audio_generation"
