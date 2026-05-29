from runner.config import load_agents, load_budgets, load_automation_level

def test_load_agents_returns_agent_list():
    data = load_agents()
    assert "agents" in data
    assert any(a["role_id"] == "manager" for a in data["agents"])

def test_load_budgets_returns_daily_limit():
    data = load_budgets()
    assert data["budgets"]["daily_limits"]["total_spend_limit_usd"] == 80.0

def test_load_automation_level_returns_level():
    data = load_automation_level()
    assert data["automation"]["current_level"] == 2
