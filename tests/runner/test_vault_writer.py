# tests/runner/test_vault_writer.py
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


def test_write_vault_session_creates_file(tmp_path):
    with patch("runner.tools.vault_writer.VAULT_DIR", tmp_path):
        import importlib
        import runner.tools.vault_writer as vw
        importlib.reload(vw)
        vw.write_vault_session(
            "TEST-001",
            "social_media_worker",
            {
                "output": "produced a great video script",
                "cost_usd": 0.0012,
                "input_tokens": 200,
                "output_tokens": 80,
            },
        )
    today = datetime.now().strftime("%Y-%m-%d")
    path = tmp_path / "sessions" / today / "TEST-001.md"
    assert path.exists(), "session file not created"
    content = path.read_text()
    assert "TEST-001" in content
    assert "social_media_worker" in content
    assert "done" in content
    assert "$0.0012" in content


def test_write_vault_session_marks_failed_on_error(tmp_path):
    with patch("runner.tools.vault_writer.VAULT_DIR", tmp_path):
        import importlib
        import runner.tools.vault_writer as vw
        importlib.reload(vw)
        vw.write_vault_session(
            "TEST-002",
            "debug_worker",
            {"error": "API timeout after 30s", "task_id": "TEST-002"},
        )
    today = datetime.now().strftime("%Y-%m-%d")
    content = (tmp_path / "sessions" / today / "TEST-002.md").read_text()
    assert "failed" in content
    assert "API timeout after 30s" in content


def test_write_vault_session_truncates_long_output(tmp_path):
    with patch("runner.tools.vault_writer.VAULT_DIR", tmp_path):
        import importlib
        import runner.tools.vault_writer as vw
        importlib.reload(vw)
        vw.write_vault_session(
            "TEST-003",
            "content_worker",
            {"output": "x" * 2000, "cost_usd": 0.001, "input_tokens": 100, "output_tokens": 400},
        )
    today = datetime.now().strftime("%Y-%m-%d")
    content = (tmp_path / "sessions" / today / "TEST-003.md").read_text()
    assert len(content) < 3000, "output not truncated"
