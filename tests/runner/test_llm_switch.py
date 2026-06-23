# tests/runner/test_llm_switch.py
import runner.agents.base as base
from runner.llm_switch import llm_disabled


def test_llm_disabled_reads_env(monkeypatch):
    monkeypatch.delenv("CC_LLM_DISABLED", raising=False)
    assert llm_disabled() is False
    for v in ("1", "true", "TRUE", "Yes", "on"):
        monkeypatch.setenv("CC_LLM_DISABLED", v)
        assert llm_disabled() is True
    for v in ("0", "false", "", "off", "no"):
        monkeypatch.setenv("CC_LLM_DISABLED", v)
        assert llm_disabled() is False


def test_agentbase_skips_when_disabled(monkeypatch):
    # With the flag set, AgentBase builds NO client (no key/network needed) and run()
    # returns a clean zero-cost skip instead of calling the provider.
    monkeypatch.setenv("CC_LLM_DISABLED", "1")
    agent = base.AgentBase("manager", "gemini-2.5-pro", "sys", tools=[])
    assert agent.client is None
    result = agent.run({"task_id": "T1", "body": "hi", "pod": "market_research_pod"})
    assert result["output"] == "(skipped — CC_LLM_DISABLED)"
    assert result["cost_usd"] == 0.0
    assert result["input_tokens"] == 0 and result["output_tokens"] == 0
    assert result["task_id"] == "T1"


def test_image_and_audio_tools_skip_when_disabled(monkeypatch):
    monkeypatch.setenv("CC_LLM_DISABLED", "1")
    from runner.tools.image import generate_image
    from runner.tools.audio import generate_audio

    assert "disabled" in generate_image("x", "f.png").get("error", "").lower()
    assert "disabled" in generate_audio("hello", "f.mp3").get("error", "").lower()
