import pytest
from pathlib import Path
from runner.automation.level_check import get_automation_level, is_action_allowed


def test_get_automation_level_returns_int(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 2\nlevel_3_actions:\n  etsy_publish: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert get_automation_level() == 2


def test_is_action_allowed_level2_blocks_level3(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 2\nlevel_3_actions:\n  etsy_publish: false\n  social_post: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert is_action_allowed("etsy_publish") is False
    assert is_action_allowed("social_post") is False


def test_is_action_allowed_when_explicitly_enabled(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 3\nlevel_3_actions:\n  etsy_publish: true\n  social_post: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert is_action_allowed("etsy_publish") is True
    assert is_action_allowed("social_post") is False


def test_is_action_allowed_listed_action_disabled_returns_false(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 3\nlevel_3_actions:\n  paid_campaign: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert is_action_allowed("paid_campaign") is False


def test_is_action_allowed_returns_true_for_level2_actions(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 2\nlevel_3_actions:\n  etsy_publish: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert is_action_allowed("content_generation") is True
