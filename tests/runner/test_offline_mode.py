"""CC_LLM_OFFLINE staging mode: $0 by construction, pipeline still runs for real."""
import json
from unittest.mock import MagicMock, patch

from runner.agents.base import AgentBase
from runner.ledger.alpaca_paper import plan_orders
from runner.tools.tony_verdict import TOOL_SPEC


def _isolate_ledger(monkeypatch, tmp_path):
    import runner.ledger.budget as budget
    monkeypatch.setattr(budget, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(budget, "SPEND_FILE", tmp_path / "daily-spend.json")
    return tmp_path / "daily-spend.json"


def test_offline_no_client_and_zero_spend(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_LLM_OFFLINE", "1")
    spend_file = _isolate_ledger(monkeypatch, tmp_path)
    agent = AgentBase("content_worker", "gemini-2.5-flash", "system prompt")
    assert agent.client is None
    result = agent.run({"task_id": "t1", "body": "do something", "pod": "test_pod"})
    assert "[offline]" in result["output"]
    assert result["cost_usd"] == 0.0
    assert result["input_tokens"] == 0 and result["output_tokens"] == 0
    spend = json.loads(spend_file.read_text())
    assert spend["total_usd"] == 0.0


def test_offline_market_research_writes_verdict_with_levels(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_LLM_OFFLINE", "1")
    _isolate_ledger(monkeypatch, tmp_path)
    import runner.tools.tony_verdict as tv
    verdicts_file = tmp_path / "tony_stocks_verdicts.json"
    monkeypatch.setattr(tv, "VERDICTS_FILE", verdicts_file)

    agent = AgentBase("market_research_worker", "gemini-2.5-pro", "you are Tony",
                      tools=[TOOL_SPEC])
    brief = "## Watchlist\n- **NVDA:** breakout setup, last $120.50\n- **AMD:** momentum, last $98.20\n"
    result = agent.run({"task_id": "tony-1", "body": brief, "pod": "market_research_pod"})

    assert result["cost_usd"] == 0.0
    verdicts = json.loads(verdicts_file.read_text())
    syms = {v["symbol"] for v in verdicts}
    assert {"NVDA", "AMD"} <= syms
    for v in verdicts:
        assert v["target"] and v["stop"] and float(v["target"]) > float(v["stop"])


def test_offline_verdicts_survive_never_open_naked_guard(tmp_path, monkeypatch):
    """An offline cycle with EMPTY scanner_levels must still plan at least one buy —
    pins the interaction with plan_orders' no-levels skip (the aa6f9c2 guard)."""
    monkeypatch.setenv("CC_LLM_OFFLINE", "1")
    _isolate_ledger(monkeypatch, tmp_path)
    import runner.tools.tony_verdict as tv
    verdicts_file = tmp_path / "tony_stocks_verdicts.json"
    monkeypatch.setattr(tv, "VERDICTS_FILE", verdicts_file)

    agent = AgentBase("market_research_worker", "gemini-2.5-pro", "you are Tony",
                      tools=[TOOL_SPEC])
    agent.run({"task_id": "tony-2", "body": "- **MSFT:** steady climber $410.00"})

    verdicts = json.loads(verdicts_file.read_text())
    plan = plan_orders(verdicts, already_done=set(), scanner_levels={})
    buys = [p for p in plan if p["action"] == "buy"]
    assert buys, "offline canned verdicts must carry target/stop so buys survive the guard"
    assert buys[0]["target"] > buys[0]["stop"]


def test_offline_no_brief_symbols_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("CC_LLM_OFFLINE", "1")
    _isolate_ledger(monkeypatch, tmp_path)
    import runner.tools.tony_verdict as tv
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    agent = AgentBase("market_research_worker", "gemini-2.5-pro", "tony", tools=[TOOL_SPEC])
    agent.run({"task_id": "tony-3", "body": "no tickers here"})
    verdicts = json.loads((tmp_path / "v.json").read_text())
    assert verdicts[0]["symbol"] == "SPY"
    assert float(verdicts[0]["target"]) > float(verdicts[0]["stop"])


def test_flag_unset_prod_path_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("CC_LLM_OFFLINE", raising=False)
    _isolate_ledger(monkeypatch, tmp_path)
    mock_client = MagicMock()
    msg = MagicMock()
    msg.content = "real model answer"
    msg.tool_calls = None
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    mock_client.chat.completions.create.return_value = resp

    with patch("runner.agents.base.openai.OpenAI", return_value=mock_client):
        agent = AgentBase("content_worker", "gemini-2.5-flash", "system prompt")
        assert agent.client is mock_client
        result = agent.run({"task_id": "t2", "body": "real task"})

    mock_client.chat.completions.create.assert_called()
    assert result["output"] == "real model answer"
    assert result["cost_usd"] > 0.0
