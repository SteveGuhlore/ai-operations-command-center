import httpx
import pytest

from runner.tools import notify as nf
from runner.ledger.alpaca_paper import closed_positions


class _R:
    def raise_for_status(self):
        pass


def _capture(monkeypatch):
    sent = {}
    def _post(url, json=None, timeout=None):
        sent["url"] = url
        sent.update(json or {})
        return _R()
    monkeypatch.setattr(nf.httpx, "post", _post)
    return sent


def test_off_is_noop(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "off")
    assert nf.notify("hi")["sent"] is False


def test_telegram_posts_to_configured_chat(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-5109399403")
    sent = _capture(monkeypatch)
    assert nf.notify("hello")["sent"] is True
    assert sent["chat_id"] == "-5109399403"
    assert "hello" in sent["text"]
    assert "tok" in sent["url"]


def test_not_configured_is_noop(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert nf.notify("x")["sent"] is False


def test_entry_and_exit_formatting(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    # Isolate from any leaked public channel so broadcast() in notify_entry/exit no-ops here and we
    # see exactly one operator message per call (this test asserts on per-call message indices).
    monkeypatch.delenv("TELEGRAM_PUBLIC_CHANNEL_ID", raising=False)
    msgs = []
    monkeypatch.setattr(nf.httpx, "post",
                        lambda url, json=None, timeout=None: (msgs.append(json["text"]), _R())[1])
    nf.notify_entry("NVDA", 66, 100.0, 94.0, 115.0)        # default risk_pct=1.0 -> "1% of the account"
    nf.notify_exit("NVDA", 66, 114.0, 924.0, reason="target", r_mult=2.3)
    nf.notify_exit("FCX", 50, 45.0, -310.0, reason="stop")
    nf.notify_reprice("FCX", 152, 74.62, 61.88)
    assert "I bought NVDA" in msgs[0] and "$100.00" in msgs[0] and "1% of the account" in msgs[0]
    assert "100%" not in msgs[0]                            # regression guard for the label bug
    assert "I sold NVDA for a +$924 win" in msgs[1] and "price target" in msgs[1] and "2.3×" in msgs[1]
    assert "I sold FCX for a $310 loss" in msgs[2] and "safety stop" in msgs[2]
    assert "I adjusted FCX" in msgs[3] and "stop $61.88" in msgs[3] and "target $74.62" in msgs[3]


def test_long_message_is_split_under_limit(monkeypatch):
    # Telegram's hard 4096-char cap: a long write-up is sent as multiple in-limit messages.
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    posts = []
    monkeypatch.setattr(nf.httpx, "post",
                        lambda url, json=None, timeout=None: (posts.append(json["text"]), _R())[1])
    big = "\n".join(f"line {i} " + "x" * 120 for i in range(100))   # well over 4096
    assert nf.notify(big)["sent"] is True
    assert len(posts) >= 2 and all(len(p) <= 4096 for p in posts)


def test_notify_chat_override_and_markup(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    sent = _capture(monkeypatch)
    kb = nf.inline_keyboard([[("📊 Status", "cmd:status")]])
    assert nf.notify("hi", chat_id="555", reply_markup=kb)["sent"] is True
    assert sent["chat_id"] == "555"
    assert sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "cmd:status"


def test_broadcast_targets_public_channel(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "-100777")
    sent = _capture(monkeypatch)
    assert nf.broadcast("public news")["sent"] is True
    assert sent["chat_id"] == "-100777"


def test_broadcast_noop_without_channel(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.delenv("TELEGRAM_PUBLIC_CHANNEL_ID", raising=False)
    assert nf.broadcast("x")["sent"] is False


def test_network_error_soft_fails(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

    def _boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(nf.httpx, "post", _boom)
    assert nf.notify("x")["sent"] is False   # never raises into the trading path


def test_closed_positions_detects_exits():
    prior = [{"symbol": "AAA", "qty": 10, "avg_entry_price": 5.0},
             {"symbol": "BBB", "qty": 5, "avg_entry_price": 9.0}]
    current = [{"symbol": "AAA", "qty": 10}]            # BBB gone
    assert [c["symbol"] for c in closed_positions(prior, current)] == ["BBB"]
    assert closed_positions(prior, prior) == []          # nothing closed when all still held
    assert closed_positions([], current) == []           # first run: no false exits
