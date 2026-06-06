import json
from datetime import date

from runner.ledger import tony_realized as tr


def test_infer_reason_target_and_stop():
    # exit at/above the target -> target; at/below the stop -> stop
    assert tr.infer_reason(exit_price=30.0, target=30.0, stop=25.0) == "target"
    assert tr.infer_reason(exit_price=31.0, target=30.0, stop=25.0) == "target"
    assert tr.infer_reason(exit_price=25.0, target=30.0, stop=25.0) == "stop"
    assert tr.infer_reason(exit_price=24.0, target=30.0, stop=25.0) == "stop"
    # between the levels -> a discretionary close
    assert tr.infer_reason(exit_price=27.5, target=30.0, stop=25.0) == "close"
    # no levels known -> unknown
    assert tr.infer_reason(exit_price=27.5, target=None, stop=None) == "unknown"


def test_record_realized_appends(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "REALIZED_FILE", tmp_path / "realized.json")
    tr.record_realized("AAA", qty=10, entry=20.0, exit_price=30.0, target=30.0, stop=15.0)
    tr.record_realized("BBB", qty=5, entry=50.0, exit_price=45.0, target=60.0, stop=45.0)
    rows = json.load(open(tmp_path / "realized.json"))
    assert len(rows) == 2
    a = rows[0]
    assert a["symbol"] == "AAA" and a["realized_pl"] == 100.0
    assert a["reason"] == "target" and a["pct"] == 50.0
    assert a["date"] == str(date.today())
    assert rows[1]["symbol"] == "BBB" and rows[1]["realized_pl"] == -25.0
    assert rows[1]["reason"] == "stop"


def test_summary_today_and_all_time(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "REALIZED_FILE", tmp_path / "realized.json")
    today = str(date.today())
    rows = [
        {"symbol": "A", "qty": 1, "entry": 10, "exit": 12, "realized_pl": 2.0, "pct": 20.0,
         "reason": "target", "date": today},
        {"symbol": "B", "qty": 1, "entry": 10, "exit": 9, "realized_pl": -1.0, "pct": -10.0,
         "reason": "stop", "date": today},
        {"symbol": "C", "qty": 1, "entry": 10, "exit": 11, "realized_pl": 1.0, "pct": 10.0,
         "reason": "close", "date": "2026-01-01"},
    ]
    (tmp_path / "realized.json").write_text(json.dumps(rows))
    s = tr.summary()
    assert s["today"]["count"] == 2
    assert s["today"]["wins"] == 1 and s["today"]["losses"] == 1
    assert s["today"]["realized_pl"] == 1.0
    assert s["all_time"]["count"] == 3
    assert s["all_time"]["realized_pl"] == 2.0
    assert s["all_time"]["by_reason"]["target"] == 1
    assert s["all_time"]["by_reason"]["stop"] == 1


def test_summary_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "REALIZED_FILE", tmp_path / "realized.json")
    s = tr.summary()
    assert s["today"]["count"] == 0 and s["all_time"]["count"] == 0
    assert s["today"]["realized_pl"] == 0.0
