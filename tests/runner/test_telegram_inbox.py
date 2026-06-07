import json

import httpx
import pytest

from runner.tools import telegram_inbox as ti


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(ti, "STATE_FILE", tmp_path / "telegram-inbox-state.json")
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TONY_TELEGRAM_CHAT", "on")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    monkeypatch.setenv("TONY_PUBLIC", "off")
    yield


def test_disabled_when_flag_off(monkeypatch):
    monkeypatch.setenv("TONY_TELEGRAM_CHAT", "off")
    assert ti.poll_and_handle()["reason"] == "disabled"


def test_reply_routing_help_and_glossary(monkeypatch):
    assert "I'm Tony" in ti.reply_for("/help")["text"]
    assert "glossary" in ti.reply_for("/glossary")["text"].lower()
    assert "/help" in ti.reply_for("/random")["text"]   # unknown command -> nudge to help


def test_reply_routing_dispatches_commands(monkeypatch):
    monkeypatch.setattr(ti, "_status_reply", lambda: "STATUS_OK")
    monkeypatch.setattr(ti, "_record_reply",
                        lambda page=0: {"text": "RECORD_OK", "has_more": False, "page": 0})
    monkeypatch.setattr(ti, "_explain_reply", lambda a: f"EXPLAIN:{a}")
    assert ti.reply_for("/status")["text"] == "STATUS_OK"
    assert ti.reply_for("/record")["text"] == "RECORD_OK"
    assert ti.reply_for("/explain NVDA")["text"] == "EXPLAIN:NVDA"
    assert ti.reply_for("/status@TonyBot")["text"] == "STATUS_OK"  # group-style mention tolerated


def test_public_tier_blocks_operator_only_command():
    rep = ti.reply_for("/watchlist", tier="public")
    assert "operator" in rep["text"].lower()


def _mock_updates(monkeypatch, updates, sent, posted):
    def _get(url, params=None, timeout=None):
        class _R:
            def raise_for_status(self): pass
            def json(self): return {"ok": True, "result": updates}
        sent["offset"] = params.get("offset")
        return _R()
    monkeypatch.setattr(ti.httpx, "get", _get)
    from runner.tools import notify as nf
    class _PR:
        def raise_for_status(self): pass
    monkeypatch.setattr(nf.httpx, "post",
                        lambda url, json=None, timeout=None: (posted.append(json), _PR())[1])


def test_whitelist_ignores_other_chats_but_advances_offset(monkeypatch):
    sent, posted = {}, []
    updates = [{"update_id": 41, "message": {"chat": {"id": 111}, "from": {"id": 111}, "text": "/status"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    res = ti.poll_and_handle()
    assert res["handled"] == 0 and posted == [] and ti._read_offset() == 42


def test_handles_operator_and_dedups(monkeypatch):
    sent, posted = {}, []
    updates = [{"update_id": 50, "message": {"chat": {"id": 999}, "from": {"id": 999}, "text": "/help"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    res = ti.poll_and_handle()
    assert res["handled"] == 1 and "I'm Tony" in posted[0]["text"] and ti._read_offset() == 51
    posted.clear()
    ti.poll_and_handle()
    assert sent["offset"] == 51          # next poll requests from the advanced offset


def test_public_command_runs_when_public_on(monkeypatch):
    monkeypatch.setenv("TONY_PUBLIC", "on")
    monkeypatch.setattr(ti, "_status_reply", lambda: "STATUS_OK")
    sent, posted = {}, []
    updates = [{"update_id": 60, "message": {"chat": {"id": 111}, "from": {"id": 111}, "text": "/status"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    res = ti.poll_and_handle()
    assert res["handled"] == 1
    assert posted[-1]["chat_id"] == "111"           # replied to the stranger's own chat
    assert ti._read_offset() == 61


def test_public_off_ignores_stranger_but_advances(monkeypatch):
    sent, posted = {}, []
    updates = [{"update_id": 70, "message": {"chat": {"id": 111}, "from": {"id": 111}, "text": "/status"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    assert ti.poll_and_handle()["handled"] == 0
    assert posted == [] and ti._read_offset() == 71


def test_public_nl_rate_limited_uses_canned(monkeypatch):
    monkeypatch.setenv("TONY_PUBLIC", "on")
    from runner.tools import telegram_policy as tp
    monkeypatch.setattr(tp, "allow_nl", lambda uid, now=None: False)   # over budget
    monkeypatch.setattr(tp, "faq_answer", lambda t: None)
    sent, posted = {}, []
    updates = [{"update_id": 80, "message": {"chat": {"id": 111}, "from": {"id": 111}, "text": "how are you feeling?"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    ti.poll_and_handle()
    low = posted[-1]["text"].lower()
    assert "tap" in low or "command" in low


def test_offset_stops_on_send_failure(monkeypatch):
    updates = [{"update_id": 90, "message": {"chat": {"id": 999}, "from": {"id": 999}, "text": "/help"}},
               {"update_id": 91, "message": {"chat": {"id": 999}, "from": {"id": 999}, "text": "/help"}}]
    def _get(url, params=None, timeout=None):
        class _R:
            def raise_for_status(self): pass
            def json(self): return {"ok": True, "result": updates}
        return _R()
    monkeypatch.setattr(ti.httpx, "get", _get)
    calls = {"n": 0}
    def _flaky(*a, **k):                       # first send ok, second fails
        calls["n"] += 1
        return {"sent": True} if calls["n"] == 1 else {"sent": False, "reason": "boom"}
    monkeypatch.setattr(ti, "notify", _flaky)
    ti.poll_and_handle()
    assert ti._read_offset() == 91             # advanced past 90 (sent), stopped at 91 (failed)


def test_callback_record_paging(monkeypatch):
    edits = []
    monkeypatch.setattr(ti, "edit_message_text",
                        lambda chat_id, message_id, text, **k: edits.append((chat_id, text)) or {"sent": True})
    monkeypatch.setattr(ti, "answer_callback_query", lambda cid: {"sent": True})
    monkeypatch.setattr(ti, "_record_rows",
                        lambda: [{"symbol": f"S{i}", "realized_pl": 1, "reason": "target", "date": "2026-06-05"} for i in range(20)])
    monkeypatch.setattr(ti, "_realized_summary_safe",
                        lambda: {"all_time": {"count": 20, "wins": 20, "losses": 0, "realized_pl": 20, "by_reason": {}}})
    updates = [{"update_id": 95, "callback_query": {"id": "cb1", "data": "rec:1",
               "message": {"message_id": 7, "chat": {"id": 999}}, "from": {"id": 999}}}]
    def _get(url, params=None, timeout=None):
        class _R:
            def raise_for_status(self): pass
            def json(self): return {"ok": True, "result": updates}
        return _R()
    monkeypatch.setattr(ti.httpx, "get", _get)
    ti.poll_and_handle()
    assert edits and "S12" in edits[-1][1]      # page 1 shows the 13th+ rows


def test_fetch_error_is_soft(monkeypatch):
    def _boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(ti.httpx, "get", _boom)
    assert ti.poll_and_handle()["reason"] == "fetch_failed"


def test_start_poller_is_idempotent(monkeypatch):
    monkeypatch.setattr(ti, "_chat_enabled", lambda: True)
    monkeypatch.setattr(ti, "_poll_loop", lambda: None)   # don't actually loop
    ti._POLLER_STARTED = False
    t1 = ti.start_poller()
    t2 = ti.start_poller()
    assert t1 is not None and t2 is t1                     # only one thread ever starts
    ti._POLLER_STARTED = False                              # reset for other tests


def test_operator_freetext_skips_faq_uses_llm(monkeypatch):
    # C: a broad FAQ keyword must NOT hijack the operator's question; it reaches the LLM.
    from runner.tools import telegram_policy as tp
    from runner.tools import tony_synthesis as ts
    monkeypatch.setattr(tp, "faq_answer", lambda t: "CANNED")        # would hijack if consulted
    monkeypatch.setattr(ts, "synth_enabled", lambda: True)
    monkeypatch.setattr(ts, "answer", lambda q, public=True: "REAL_ANSWER")
    assert ti.reply_for("what stocks do you have?", tier="operator")["text"] == "REAL_ANSWER"


def test_public_freetext_still_uses_faq(monkeypatch):
    # C: the public tier still gets the canned FAQ (the cost saver) before any LLM call.
    monkeypatch.setenv("TONY_PUBLIC", "on")
    from runner.tools import telegram_policy as tp
    monkeypatch.setattr(tp, "faq_answer", lambda t: "CANNED")
    assert ti.reply_for("are you real money?", tier="public", user_id="5")["text"] == "CANNED"


def test_nl_off_message_is_distinct(monkeypatch):
    # F: when synthesis is off, say so distinctly instead of a generic deflection.
    from runner.tools import tony_synthesis as ts
    monkeypatch.setattr(ts, "synth_enabled", lambda: False)
    assert "off" in ti.reply_for("how's it going?", tier="operator")["text"].lower()


def test_explain_no_arg_lists_current_names(monkeypatch):
    # D: /explain with no symbol lists what Tony actually has, so the user never guesses.
    monkeypatch.setattr(ti, "_current_names", lambda limit=12: ["ANET", "CSX"])
    rep = ti.reply_for("/explain")
    assert "ANET" in rep["text"] and "explain" in rep["text"].lower()


def test_explain_unknown_symbol_offers_discovery(monkeypatch):
    # E: an unknown symbol points the user at the names Tony does have, not a dead-end.
    monkeypatch.setattr(ti, "_current_names", lambda limit=12: ["ANET", "CSX"])
    from runner.ledger import alpaca_paper as ap
    monkeypatch.setattr(ap, "_verdict_thesis", lambda verdicts, sym: "")
    monkeypatch.setattr(ap, "account_record", lambda: {"open_positions": []})
    rep = ti.reply_for("/explain ZZZZ")
    assert "ZZZZ" in rep["text"] and "ANET" in rep["text"]
