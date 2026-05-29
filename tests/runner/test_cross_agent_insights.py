# tests/runner/test_cross_agent_insights.py
import importlib


def _fresh(tmp_path, monkeypatch):
    import runner.tools.vault_memory as vm
    importlib.reload(vm)
    monkeypatch.setattr(vm, "SYNTHESIS_DIR", tmp_path)
    return vm


_BODY = (
    "# Cross-Agent Insights\n\n"
    "## System-Wide Patterns\n- web_research returns structured emails/handles now.\n"
)


def test_missing_file_returns_empty(tmp_path, monkeypatch):
    vm = _fresh(tmp_path, monkeypatch)
    assert vm.load_cross_agent_insights() == ""


def test_frontmatter_stripped(tmp_path, monkeypatch):
    vm = _fresh(tmp_path, monkeypatch)
    (tmp_path / "cross_agent_insights.md").write_text(
        "---\ntags: [agent-memory]\n---\n" + _BODY, encoding="utf-8")
    out = vm.load_cross_agent_insights()
    assert out.startswith("# Cross-Agent Insights")
    assert "tags:" not in out
    assert "web_research" in out


def test_short_content_ignored(tmp_path, monkeypatch):
    vm = _fresh(tmp_path, monkeypatch)
    (tmp_path / "cross_agent_insights.md").write_text("tiny", encoding="utf-8")
    assert vm.load_cross_agent_insights() == ""


def test_bounded_to_max_chars(tmp_path, monkeypatch):
    vm = _fresh(tmp_path, monkeypatch)
    big = "# Insights\n" + "\n".join(f"- line {i} with some words" for i in range(500))
    (tmp_path / "cross_agent_insights.md").write_text(big, encoding="utf-8")
    out = vm.load_cross_agent_insights()
    assert len(out) <= vm._MAX_INSIGHTS_CHARS + len("\n…(truncated)")
    assert out.endswith("…(truncated)")


def test_injected_into_system_prompt(tmp_path, monkeypatch):
    """The whole point of D3: insights reach an agent's live prompt."""
    import runner.tools.vault_memory as vm
    importlib.reload(vm)
    monkeypatch.setattr(vm, "SYNTHESIS_DIR", tmp_path)
    (tmp_path / "cross_agent_insights.md").write_text(_BODY, encoding="utf-8")

    import runner.agents.prompts as prompts
    importlib.reload(prompts)
    monkeypatch.setattr(prompts, "load_cross_agent_insights", vm.load_cross_agent_insights)

    p = prompts.build_system_prompt("outreach_worker")
    assert "Cross-Agent Insights (system-wide" in p
    assert "web_research" in p
