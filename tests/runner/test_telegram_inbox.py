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
    yield


def test_disabled_when_flag_off(monkeypatch):
    monkeypatch.setenv("TONY_TELEGRAM_CHAT", "off")
    assert ti.poll_and_handle()["reason"] == "disabled"


def test_reply_routing_help_and_glossary(monkeypatch):
    assert "I'm Tony" in ti.reply_for("/help")
    assert "glossary" in ti.reply_for("/glossary").lower()
    assert "/help" in ti.reply_for("random gibberish")  # unknown -> nudge to help


def test_reply_routing_dispatches_commands(monkeypatch):
    monkeypatch.setattr(ti, "_status_reply", lambda: "STATUS_OK")
    monkeypatch.setattr(ti, "_record_reply", lambda: "RECORD_OK")
    monkeypatch.setattr(ti, "_explain_reply", lambda a: f"EXPLAIN:{a}")
    assert ti.reply_for("/status") == "STATUS_OK"
    assert ti.reply_for("/record") == "RECORD_OK"
    assert ti.reply_for("/explain NVDA") == "EXPLAIN:NVDA"
    assert ti.reply_for("/status@TonyBot") == "STATUS_OK"  # group-style mention tolerated


def _mock_updates(monkeypatch, updates, sent, posted):
    def _get(url, params=None, timeout=None):
        class _R:
            def raise_for_status(self): pass
            def json(self): return {"ok": True, "result": updates}
        sent["offset"] = params.get("offset")
        return _R()
    monkeypatch.setattr(ti.httpx, "get", _get)
    # capture outbound replies via notify's httpx.post
    from runner.tools import notify as nf
    class _PR:
        def raise_for_status(self): pass
    monkeypatch.setattr(nf.httpx, "post",
                        lambda url, json=None, timeout=None: (posted.append(json), _PR())[1])


def test_whitelist_ignores_other_chats_but_advances_offset(monkeypatch):
    sent, posted = {}, []
    updates = [{"update_id": 41, "message": {"chat": {"id": 111}, "text": "/status"}}]  # stranger
    _mock_updates(monkeypatch, updates, sent, posted)
    res = ti.poll_and_handle()
    assert res["handled"] == 0          # stranger ignored
    assert posted == []                  # no reply sent
    assert ti._read_offset() == 42       # but offset advances so we don't re-fetch it


def test_handles_operator_and_dedups(monkeypatch):
    sent, posted = {}, []
    updates = [{"update_id": 50, "message": {"chat": {"id": 999}, "text": "/help"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    res = ti.poll_and_handle()
    assert res["handled"] == 1
    assert len(posted) == 1 and "I'm Tony" in posted[0]["text"]
    assert ti._read_offset() == 51
    # next poll must request from the advanced offset (no reprocessing)
    posted.clear()
    ti.poll_and_handle()
    assert sent["offset"] == 51


def test_fetch_error_is_soft(monkeypatch):
    def _boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(ti.httpx, "get", _boom)
    assert ti.poll_and_handle()["reason"] == "fetch_failed"
