"""account_mode tests (Phase 2): paper is the default; going live is fail-closed and requires an
ISOLATED live account. No test enables real trading — these assert the guard REFUSES."""
import pytest

from runner.ledger import account_mode as am


def _passing_record():
    return {"graded": 100, "tony_win_rate": 75.0}


def test_default_is_paper(monkeypatch):
    monkeypatch.delenv("TONY_ACCOUNT_MODE", raising=False)
    assert am.account_mode() == "paper" and am.is_paper() and not am.is_live()
    assert am.money_label() == "paper"


def test_live_label_and_mode(monkeypatch):
    monkeypatch.setenv("TONY_ACCOUNT_MODE", "live")
    assert am.is_live() and am.money_label() == "real"


def test_live_preconditions_blocks_in_paper_mode(monkeypatch):
    monkeypatch.delenv("TONY_ACCOUNT_MODE", raising=False)
    g = am.live_preconditions(_passing_record())
    assert g["ready"] is False and any("not 'live'" in r for r in g["reasons"])


def test_live_preconditions_requires_isolated_keys(monkeypatch):
    monkeypatch.setenv("TONY_ACCOUNT_MODE", "live")
    monkeypatch.setenv("TONY_LIVE_ENABLED", "1")
    monkeypatch.delenv("TONY_KILL_SWITCH", raising=False)
    # same key for bot and live -> isolation failure
    monkeypatch.setenv("ALPACA_API_KEY", "SAMEKEY")
    monkeypatch.setenv("TONY_LIVE_ALPACA_API_KEY", "SAMEKEY")
    monkeypatch.setenv("TONY_LIVE_ALPACA_SECRET_KEY", "s")
    g = am.live_preconditions(_passing_record())
    assert g["ready"] is False and any("not isolated" in r for r in g["reasons"])


def test_live_preconditions_blocks_when_credentials_missing(monkeypatch):
    monkeypatch.setenv("TONY_ACCOUNT_MODE", "live")
    monkeypatch.setenv("TONY_LIVE_ENABLED", "1")
    monkeypatch.delenv("TONY_LIVE_ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("TONY_LIVE_ALPACA_SECRET_KEY", raising=False)
    g = am.live_preconditions(_passing_record())
    assert g["ready"] is False and any("credentials not provided" in r for r in g["reasons"])


def test_live_preconditions_propagates_track_record_guard(monkeypatch):
    # thin record must still block even with everything else set (defense in depth)
    monkeypatch.setenv("TONY_ACCOUNT_MODE", "live")
    monkeypatch.setenv("TONY_LIVE_ENABLED", "1")
    monkeypatch.setenv("TONY_LIVE_ALPACA_API_KEY", "LIVEKEY")
    monkeypatch.setenv("TONY_LIVE_ALPACA_SECRET_KEY", "s")
    monkeypatch.setenv("ALPACA_API_KEY", "BOTKEY")
    g = am.live_preconditions({"graded": 2, "tony_win_rate": 10.0})
    assert g["ready"] is False
    assert any("track record" in r or "win rate" in r for r in g["reasons"])
