import pytest

from runner import config
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


# --- DESLOPPIFY C5: config load is a validation boundary ---------------------


def _write_budgets(tmp_path, monkeypatch, text):
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "budgets.yaml").write_text(text, encoding="utf-8")


def test_load_budgets_empty_file_raises(tmp_path, monkeypatch):
    # An empty/truncated budgets.yaml must fail loudly, not parse to None and let
    # the spend cap read as "uncapped" on a live 24/7 trader.
    _write_budgets(tmp_path, monkeypatch, "")
    with pytest.raises(ValueError):
        config.load_budgets()


def test_load_budgets_missing_cap_raises(tmp_path, monkeypatch):
    _write_budgets(tmp_path, monkeypatch, "budgets:\n  daily_limits: {}\n")
    with pytest.raises(ValueError):
        config.load_budgets()


@pytest.mark.parametrize("val", ["0", "-5", "abc", "true"])
def test_load_budgets_bad_cap_raises(tmp_path, monkeypatch, val):
    _write_budgets(
        tmp_path,
        monkeypatch,
        f"budgets:\n  daily_limits:\n    total_spend_limit_usd: {val}\n",
    )
    with pytest.raises(ValueError):
        config.load_budgets()


def test_load_non_mapping_raises(tmp_path, monkeypatch):
    _write_budgets(tmp_path, monkeypatch, "- just\n- a\n- list\n")
    with pytest.raises(ValueError):
        config.load_budgets()
