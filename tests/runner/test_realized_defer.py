import json

from runner.ledger import alpaca_paper as ap
from runner.ledger import tony_realized as tr


class _Broker:
    """Minimal broker: AAA was held last cycle and is gone now (closed)."""

    def __init__(self, price):
        self.price = price

    def account(self):
        return {"open_positions": []}

    def _latest_price(self, symbol):
        return self.price


def test_unpriced_exit_is_deferred_then_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "NOTIFY_STATE", tmp_path / "notify.json")
    monkeypatch.setattr(ap, "_latest_scanner_levels", lambda: {})
    monkeypatch.setattr(tr, "REALIZED_FILE", tmp_path / "realized.json")
    ap.NOTIFY_STATE.write_text(
        json.dumps([{"symbol": "AAA", "qty": 10, "avg_entry_price": 100.0}])
    )

    # Cycle 1: exit price unavailable -> NOT recorded, but kept in the snapshot to retry.
    ap._notify_closed(_Broker(None))
    assert tr._load() == []  # the stop-out is not silently dropped...
    snap = json.loads(ap.NOTIFY_STATE.read_text())
    assert any(p["symbol"] == "AAA" for p in snap)  # ...it is deferred, still owed a record

    # Cycle 2: price now available -> recorded once, dropped from the snapshot.
    ap._notify_closed(_Broker(95.0))
    rows = tr._load()
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAA"
    assert rows[0]["realized_pl"] == -50.0  # (95-100)*10
    snap2 = json.loads(ap.NOTIFY_STATE.read_text())
    assert not any(p["symbol"] == "AAA" for p in snap2)
