import httpx

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
    msgs = []
    monkeypatch.setattr(nf.httpx, "post",
                        lambda url, json=None, timeout=None: (msgs.append(json["text"]), _R())[1])
    nf.notify_entry("NVDA", 66, 100.0, 94.0, 115.0)
    nf.notify_exit("NVDA", 66, 114.0, 924.0)
    nf.notify_exit("FCX", 50, 45.0, -310.0)
    assert "entered NVDA" in msgs[0] and "$100.00" in msgs[0] and "1% risk" in msgs[0]
    assert "closed NVDA" in msgs[1] and "+$924" in msgs[1]
    assert "closed FCX" in msgs[2] and "-$310" in msgs[2]


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
