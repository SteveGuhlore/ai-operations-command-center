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


def test_whole_share_qty():
    # bracket orders can't be fractional — notional must become a whole-share qty
    assert ap.whole_share_qty(1000, 50) == 20
    assert ap.whole_share_qty(1000, 333) == 3      # floors
    assert ap.whole_share_qty(1000, 1500) == 1     # share dearer than budget -> at least 1
    assert ap.whole_share_qty(1000, None) == 1     # no price -> fall back to 1
    assert ap.whole_share_qty(1000, 0) == 1        # no div-by-zero


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


def test_parse_scanner_levels():
    md = (
        "### [[D]]\n"
        "- Last close: $66.96 | Target: $71.7386 (+7.1%) | Stop: $64.5707 (-3.6%)\n"
        "### [[ZETA]]\n"
        "- Last close: $18.8 | Target: $21.6768 (+15.3%) | Stop: $17.3616 (-7.7%)\n"
    )
    lv = ap.parse_scanner_levels(md)
    assert lv["D"] == {"target": 71.7386, "stop": 64.5707}
    assert lv["ZETA"]["target"] == 21.6768


def test_reaffirm_inherits_scanner_levels():
    # reaffirm carries no levels of its own -> must inherit the scanner's for a protected bracket
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "reaffirm"}]
    plan = ap.plan_orders(verdicts, set(), {"AAA": {"target": 30.0, "stop": 25.0}})
    assert plan[0]["target"] == 30.0 and plan[0]["stop"] == 25.0


def test_own_levels_beat_scanner():
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "adjust", "target": 40, "stop": 35}]
    plan = ap.plan_orders(verdicts, set(), {"AAA": {"target": 30.0, "stop": 25.0}})
    assert plan[0]["target"] == 40 and plan[0]["stop"] == 35


def test_plan_skips_already_done():
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "reaffirm"}]
    assert ap.plan_orders(verdicts, {"2026-06-03:AAA:open"}) == []


def test_plan_skips_degenerate_bracket():
    # target <= stop is an invalid long bracket (Alpaca rejects) -> must not be planned
    verdicts = [
        {"date": "2026-06-03", "symbol": "D", "verdict": "override", "target": 66.53, "stop": 66.53},
        {"date": "2026-06-03", "symbol": "HOOD", "verdict": "override", "target": 99.0, "stop": 76.0},
    ]
    syms = {p["symbol"] for p in ap.plan_orders(verdicts, set())}
    assert syms == {"HOOD"}  # D dropped, HOOD kept


def test_intraday_close_fires_after_open():
    # buying AAA in the morning must NOT block a later same-day discretionary close
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "close"}]
    plan = ap.plan_orders(verdicts, {"2026-06-03:AAA:open"})
    assert plan == [{"key": "2026-06-03:AAA:close", "symbol": "AAA", "action": "close"}]


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


def test_paper_book_no_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    book = ap.paper_book()
    assert book["status"] == "no_keys" and book["orders"] == [] and book["open_positions"] == []


def test_flush_session_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    (tmp_path / "exec.json").write_text(json.dumps(["2026-06-02:D:open"]))
    (tmp_path / "v.json").write_text(json.dumps([{"date": "2026-06-02", "symbol": "D"}]))

    class CancelBroker:
        cancelled = False
        def cancel_all(self):
            CancelBroker.cancelled = True

    res = ap.flush_session(broker=CancelBroker())
    assert CancelBroker.cancelled and res["cancelled"] == "ok"
    assert json.load(open(tmp_path / "exec.json")) == []
    assert json.load(open(tmp_path / "v.json")) == []


def test_flush_session_no_keys_still_clears(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    (tmp_path / "exec.json").write_text("[]")
    (tmp_path / "v.json").write_text("[]")
    res = ap.flush_session()
    assert res["cancelled"] == "no_keys" and "v.json" in res["cleared"]
