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


def test_reads_newest_nonempty_day(tmp_path, monkeypatch):
    # the 2 AM hook used to read 'today' (empty at 2 AM) -> nightly self-improvement silently skipped
    import scripts.improvement_loop as il
    s = tmp_path / "sessions"
    (s / "2026-06-11").mkdir(parents=True)                       # "today" at 2 AM — empty
    (s / "2026-06-10").mkdir(); (s / "2026-06-10" / "t1.md").write_text("YESTERDAY_WORK")
    (s / "2026-06-09").mkdir(); (s / "2026-06-09" / "t0.md").write_text("OLDER")
    monkeypatch.setattr(il, "VAULT_DIR", tmp_path)
    out = il._read_recent_sessions()
    assert "YESTERDAY_WORK" in out and "OLDER" not in out


def test_read_recent_sessions_empty(tmp_path, monkeypatch):
    import scripts.improvement_loop as il
    (tmp_path / "sessions").mkdir()
    monkeypatch.setattr(il, "VAULT_DIR", tmp_path)
    assert il._read_recent_sessions() == ""
