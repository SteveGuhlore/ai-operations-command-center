import json
from runner.ledger import alpaca_paper as ap


class FakeBroker:
    def __init__(self):
        self.buys = []
        self.closes = []

    def buy(self, symbol, notional, target, stop):
        self.buys.append((symbol, notional, target, stop))

    def close(self, symbol):
        self.closes.append(symbol)

    def account(self):
        return {"equity": 100000.0, "open_positions": []}


def test_plan_opens_and_closes():
    verdicts = [
        {"date": "2026-06-03", "symbol": "AAA", "verdict": "override", "target": 30, "stop": 25},
        {"date": "2026-06-03", "symbol": "BBB", "verdict": "reaffirm"},
        {"date": "2026-06-03", "symbol": "CCC", "verdict": "pass"},
        {"date": "2026-06-03", "symbol": "DDD", "verdict": "close"},
    ]
    plan = ap.plan_orders(verdicts, set())
    actions = {p["symbol"]: p["action"] for p in plan}
    assert actions == {"AAA": "buy", "BBB": "buy", "DDD": "close"}  # pass skipped


def test_plan_skips_already_done():
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "reaffirm"}]
    assert ap.plan_orders(verdicts, {"2026-06-03:AAA"}) == []


def test_sync_executes_and_is_idempotent(tmp_path, monkeypatch):
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "override", "target": 30, "stop": 25}]
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    b = FakeBroker()
    r1 = ap.sync(broker=b)
    assert r1["executed"] == 1 and b.buys[0][0] == "AAA"
    r2 = ap.sync(broker=b)  # second run must not re-order
    assert r2["executed"] == 0
    assert len(b.buys) == 1


def test_sync_degrades_without_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    assert ap.sync()["status"] == "no_keys"


def test_account_record_no_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    assert ap.account_record()["status"] == "no_keys"
