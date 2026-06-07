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


def test_unpriced_exit_is_deferred_then_alerted(tmp_path, monkeypatch):
    # The ledger is now reconciled from Alpaca fills, so _notify_closed's job is the ALERT. The defer
    # still matters: don't fire a phantom alert before we can price the exit; keep it in the snapshot
    # to retry, then alert once and drop it.
    import runner.tools.notify as nf
    monkeypatch.setattr(ap, "NOTIFY_STATE", tmp_path / "notify.json")
    monkeypatch.setattr(ap, "_latest_scanner_levels", lambda: {})
    alerts = []
    monkeypatch.setattr(nf, "notify_exit", lambda *a, **k: alerts.append(a) or {"sent": True})
    ap.NOTIFY_STATE.write_text(
        json.dumps([{"symbol": "AAA", "qty": 10, "avg_entry_price": 100.0}])
    )

    # Cycle 1: exit price unavailable -> NOT alerted, but kept in the snapshot to retry.
    ap._notify_closed(_Broker(None))
    assert alerts == []  # no phantom alert...
    snap = json.loads(ap.NOTIFY_STATE.read_text())
    assert any(p["symbol"] == "AAA" for p in snap)  # ...deferred, still owed an alert

    # Cycle 2: price now available -> alerted once, dropped from the snapshot.
    ap._notify_closed(_Broker(95.0))
    assert len(alerts) == 1 and alerts[0][0] == "AAA"
    snap2 = json.loads(ap.NOTIFY_STATE.read_text())
    assert not any(p["symbol"] == "AAA" for p in snap2)
