from runner.tools import tony_synthesis as ts


def test_synth_enabled_flag(monkeypatch):
    monkeypatch.setenv("TONY_SYNTH", "on")
    assert ts.synth_enabled() is True
    monkeypatch.setenv("TONY_SYNTH", "off")
    assert ts.synth_enabled() is False


def test_daily_wrap_passes_real_facts_to_model(monkeypatch):
    captured = {}
    def _fake_narrate(prompt, max_words=90):
        captured["p"] = prompt
        return "Good day, I'm up."
    monkeypatch.setattr(ts, "_narrate", _fake_narrate)
    monkeypatch.setattr(ts, "_book_facts", lambda: {
        "acct": {"status": "ok", "equity": 101200,
                 "open_positions": [{"symbol": "CARR", "unrealized_pl": 300},
                                    {"symbol": "KDP", "unrealized_pl": -50}]},
        "realized": {"today": {"count": 1, "wins": 1, "losses": 0, "realized_pl": 540}}})
    out = ts.daily_wrap()
    assert out == "Good day, I'm up."
    p = captured["p"]
    assert "CARR" in p and "KDP" in p
    assert "101200" in p and "540" in p
    assert "do not invent" in p  # guardrail against hallucinated numbers


def test_daily_wrap_empty_when_account_not_ok(monkeypatch):
    monkeypatch.setattr(ts, "_book_facts", lambda: {"acct": {"status": "err"}, "realized": {}})
    # _narrate must not even be called
    monkeypatch.setattr(ts, "_narrate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("called")))
    assert ts.daily_wrap() == ""


def test_weekly_review_empty_until_scored(monkeypatch):
    monkeypatch.setattr(ts, "_narrate", lambda *a, **k: "should not be used")
    import runner.ledger.tony_scorecard as sc
    monkeypatch.setattr(sc, "compute_record", lambda: {"status": "awaiting_outcomes", "graded": 0})
    assert ts.weekly_review() == ""


def test_send_daily_wrap_soft_when_no_narrative(monkeypatch):
    monkeypatch.setattr(ts, "daily_wrap", lambda: "")
    assert ts.send_daily_wrap()["sent"] is False


def test_send_daily_wrap_sends_when_narrative(monkeypatch):
    monkeypatch.setattr(ts, "daily_wrap", lambda: "Up nicely today.")
    sent = {}
    def _fake_notify(text, **k):
        sent["t"] = text
        return {"sent": True}
    monkeypatch.setattr("runner.tools.notify.notify", _fake_notify)
    res = ts.send_daily_wrap()
    assert res["sent"] is True
    assert "My day, in plain English" in sent["t"] and "Up nicely today." in sent["t"]
