from runner.tools import telegram_policy as tp

# Fixed midday UTC epoch so now+3601 never crosses a day boundary (avoids flakiness).
NOON = 1717848000.0   # 2024-06-08 12:00:00 UTC


def test_tier_and_operator(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    assert tp.tier_for("999") == "operator"
    assert tp.tier_for("123") == "public"
    assert tp.is_operator("999") and not tp.is_operator("123")


def test_public_command_allowlist():
    assert tp.command_allowed("status", "public")
    assert tp.command_allowed("record", "public")
    assert not tp.command_allowed("watchlist", "public")   # front-running guard
    assert tp.command_allowed("watchlist", "operator")     # operator sees everything


def test_faq_matches_known_question():
    assert "paper" in tp.faq_answer("is this real money?").lower()
    assert tp.faq_answer("what is your favorite color") is None


def test_rate_limiter_per_user_and_global(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "STATE_FILE", tmp_path / "telegram-public-state.json")
    monkeypatch.setenv("TONY_PUBLIC_NL_PER_USER_HOUR", "2")
    monkeypatch.setenv("TONY_PUBLIC_NL_DAILY_CAP", "3")
    now = NOON
    assert tp.allow_nl("u1", now)        # 1
    assert tp.allow_nl("u1", now)        # 2
    assert not tp.allow_nl("u1", now)    # 3 -> per-user cap (2/hr) hit
    assert tp.allow_nl("u2", now)        # global 3rd allowed
    assert not tp.allow_nl("u2", now)    # global daily cap (3) hit
    assert tp.allow_nl("u1", now + 3601) is False  # window rolled, but daily cap still in force
