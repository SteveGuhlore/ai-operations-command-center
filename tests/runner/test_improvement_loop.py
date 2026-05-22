# tests/runner/test_improvement_loop.py
import pytest


def test_parse_updates_extracts_changed_agent():
    from scripts.improvement_loop import _parse_updates

    response = """
AGENT: social_media_worker
CHANGED
# Spark — Updated
New improved content here.
END_AGENT

AGENT: content_worker
NO_CHANGE
END_AGENT

Summary: Updated Spark because scripts were too long.
"""
    updates, summary = _parse_updates(response)
    assert "social_media_worker" in updates
    assert "# Spark — Updated" in updates["social_media_worker"]
    assert "content_worker" not in updates
    assert "Updated Spark" in summary


def test_parse_updates_returns_empty_on_no_changes():
    from scripts.improvement_loop import _parse_updates

    response = """
AGENT: manager
NO_CHANGE
END_AGENT
"""
    updates, summary = _parse_updates(response)
    assert updates == {}


def test_parse_updates_handles_malformed_gracefully():
    from scripts.improvement_loop import _parse_updates

    updates, summary = _parse_updates("some random text with no agent blocks")
    assert updates == {}
