import pytest
from pathlib import Path
from runner.plugins.loader import load_skill, build_agent_skills_prompt


def test_load_skill_returns_content(tmp_path, monkeypatch):
    import runner.plugins.loader as loader_module
    monkeypatch.setattr(loader_module, "PLUGINS_CACHE", tmp_path)
    skill_dir = tmp_path / "superpowers" / "5.1.0" / "skills" / "systematic-debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "systematic-debugging.md").write_text("# Debug skill content", encoding="utf-8")
    result = load_skill("superpowers", "systematic-debugging")
    assert "Debug skill content" in result


def test_load_skill_returns_empty_when_missing(tmp_path, monkeypatch):
    import runner.plugins.loader as loader_module
    monkeypatch.setattr(loader_module, "PLUGINS_CACHE", tmp_path)
    result = load_skill("superpowers", "nonexistent-skill")
    assert result == ""


def test_build_agent_skills_prompt_for_debug_worker(tmp_path, monkeypatch):
    import runner.plugins.loader as loader_module
    monkeypatch.setattr(loader_module, "PLUGINS_CACHE", tmp_path)
    # No skills available — should return empty string gracefully
    result = build_agent_skills_prompt("debug_worker")
    assert isinstance(result, str)
