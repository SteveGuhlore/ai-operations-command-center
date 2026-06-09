import json
from runner.ledger import alpaca_paper as ap


class FakeBroker:
    def __init__(self, positions=None, orders=None):
        self.buys = []
        self.buy_risk_pcts = []
        self.closes = []
        self.protects = []
        self.reprices = []
        self._positions = positions or []
        self._orders = orders or []

    def buy(self, symbol, notional, target, stop, risk_pct=None):
        self.buys.append((symbol, notional, target, stop))
        self.buy_risk_pcts.append(risk_pct)

    def close(self, symbol):
        self.closes.append(symbol)

    def protect(self, symbol, qty, target, stop):
        self.protects.append((symbol, qty, target, stop))

    def reprice(self, symbol, qty, target, stop):
        self.reprices.append((symbol, qty, target, stop))

    def account(self):
        return {"equity": 100000.0, "open_positions": self._positions}

    def open_orders(self):
        return self._orders


def test_risk_based_qty_matches_bot_sizing():
    # same formula as the bot: shares = min(risk$/risk_per_share, max_notional/price), floored.
    # 1% of $1,000,000 = $10,000 risk; stop $5 below a $100 entry -> $10k/$5 = 2000 shares,
    # but capped by max_notional $5000 -> 5000/100 = 50 shares.
    assert ap.risk_based_qty(1_000_000, 100.0, 95.0, 1.0, 5000) == 50
    # wide stop so the risk cap binds before the notional cap:
    # $10k risk / ($100-$50=$50) = 200 sh; notional cap 5000/100=50 -> still 50 (cap binds)
    assert ap.risk_based_qty(1_000_000, 100.0, 50.0, 1.0, 5000) == 50
    # small account where risk binds: 1% of $20,000 = $200 risk / $5 = 40 sh; cap 5000/100=50 -> 40
    assert ap.risk_based_qty(20_000, 100.0, 95.0, 1.0, 5000) == 40
    # guards: no price / degenerate stop -> at least 1
    assert ap.risk_based_qty(1_000_000, None, 95.0, 1.0, 5000) == 1
    assert ap.risk_based_qty(1_000_000, 100.0, 100.0, 1.0, 5000) == 1  # stop>=price


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
    # AAA opens (has stop+target), DDD closes. BBB is a reaffirm with NO stop/target and no
    # scanner levels -> skipped by the never-open-naked guard. CCC (pass) is skipped.
    assert actions == {"AAA": "buy", "DDD": "close"}


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


def test_plan_skips_buy_when_already_held():
    # carried-over position: a reaffirm on a held name must NOT pyramid a second buy;
    # a new name still opens. The reconciler keeps the held position protected.
    verdicts = [
        {"date": "2026-06-04", "symbol": "AAA", "verdict": "reaffirm"},
        {"date": "2026-06-04", "symbol": "BBB", "verdict": "override", "target": 30, "stop": 25},
    ]
    plan = ap.plan_orders(verdicts, set(), {"AAA": {"target": 30.0, "stop": 25.0}}, held_symbols={"AAA"})
    assert {p["symbol"] for p in plan} == {"BBB"}


def test_plan_held_still_allows_close():
    # holding a name must not block an explicit close of it
    verdicts = [{"date": "2026-06-04", "symbol": "AAA", "verdict": "close"}]
    plan = ap.plan_orders(verdicts, set(), {}, held_symbols={"AAA"})
    assert plan == [{"key": "2026-06-04:AAA:close", "symbol": "AAA", "action": "close"}]


def test_plan_orders_caps_new_buys():
    # portfolio / daily-order parity with the bot: never emit more new buys than the room allows
    verdicts = [
        {"date": "2026-06-04", "symbol": "A", "verdict": "override", "target": 30, "stop": 25},
        {"date": "2026-06-04", "symbol": "B", "verdict": "override", "target": 30, "stop": 25},
        {"date": "2026-06-04", "symbol": "C", "verdict": "override", "target": 30, "stop": 25},
    ]
    buys = [p for p in ap.plan_orders(verdicts, set(), {}, max_new_buys=2) if p["action"] == "buy"]
    assert len(buys) == 2


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
    monkeypatch.setenv("TONY_MARKET_SESSION", "open")
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
        def cancel_entry_orders(self):
            CancelBroker.cancelled = True
            return 0

    res = ap.flush_session(broker=CancelBroker())
    assert CancelBroker.cancelled and res["cancelled"] == "ok"
    assert json.load(open(tmp_path / "exec.json")) == []
    assert json.load(open(tmp_path / "v.json")) == []


def test_entry_orders_to_cancel_keeps_protective_legs():
    # Only unfilled BUY entries get cancelled; SELL stop/target legs on held positions stay.
    orders = [
        {"symbol": "AAA", "side": "buy", "id": "1"},
        {"symbol": "BBB", "side": "sell", "id": "2"},
        {"symbol": "CCC", "side": "buy", "id": "3"},
    ]
    assert [o["id"] for o in ap.entry_orders_to_cancel(orders)] == ["1", "3"]


def test_positions_needing_protection():
    positions = [
        {"symbol": "AAA", "qty": 10.0, "unrealized_pl": 1.0},    # whole + no stop leg + levels -> protect 10
        {"symbol": "BBB", "qty": 12.0, "unrealized_pl": 0.0},    # has a STOP leg -> skip (protected)
        {"symbol": "TPONLY", "qty": 8.0, "unrealized_pl": 0.0},  # lone take-profit, NO stop -> needs protection
        {"symbol": "FRAC", "qty": 17.59, "unrealized_pl": -1.0}, # fractional -> protect the whole-share floor (17)
        {"symbol": "TINY", "qty": 0.4, "unrealized_pl": 0.0},    # sub-1-share sliver -> can't protect -> skip
        {"symbol": "NOLV", "qty": 5.0, "unrealized_pl": 0.0},    # no known levels -> skip
    ]
    orders = [{"symbol": "BBB", "side": "sell", "type": "stop", "id": "9"},
              {"symbol": "TPONLY", "side": "sell", "type": "limit", "id": "10"}]  # take-profit only, no stop
    levels = {"AAA": {"target": 30.0, "stop": 25.0}, "BBB": {"target": 50.0, "stop": 40.0},
              "TPONLY": {"target": 60.0, "stop": 50.0},
              "FRAC": {"target": 20.0, "stop": 15.0}, "TINY": {"target": 2.0, "stop": 1.0}}
    assert ap.positions_needing_protection(positions, orders, levels) == [
        {"symbol": "AAA", "qty": 10, "target": 30.0, "stop": 25.0},
        {"symbol": "TPONLY", "qty": 8, "target": 60.0, "stop": 50.0},
        {"symbol": "FRAC", "qty": 17, "target": 20.0, "stop": 15.0}]


def test_positions_needing_protection_skips_degenerate():
    positions = [{"symbol": "D", "qty": 5.0}]
    assert ap.positions_needing_protection(positions, [], {"D": {"target": 66.53, "stop": 66.53}}) == []


def test_latest_scanner_levels_uses_newest_including_intraday(tmp_path, monkeypatch):
    (tmp_path / "2026-06-03.md").write_text("### [[AAA]]\n- Target: $30.0 (+1%) | Stop: $25.0 (-1%)\n")
    (tmp_path / "2026-06-03T1530.md").write_text("### [[SLB]]\n- Target: $61.17 (+1%) | Stop: $54.6 (-1%)\n")
    monkeypatch.setattr(ap, "BRIDGE_DIR", tmp_path)
    lv = ap._latest_scanner_levels()
    assert lv.get("SLB") == {"target": 61.17, "stop": 54.6}  # intraday is newest -> used


def test_sync_reconciles_unprotected_positions(tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    (tmp_path / "v.json").write_text("[]")
    bd = tmp_path / "bridge"; bd.mkdir()
    (bd / "2026-06-03T1530.md").write_text("### [[CVS]]\n- Target: $98.06 (+1%) | Stop: $88.73 (-1%)\n")
    monkeypatch.setattr(ap, "BRIDGE_DIR", bd)
    b = FakeBroker(positions=[{"symbol": "CVS", "qty": 10.0, "unrealized_pl": 3.1}], orders=[])
    r = ap.sync(broker=b)
    assert r["protected"] == 1
    assert b.protects == [("CVS", 10, 98.06, 88.73)]


def test_plan_reprices_adjusted_held_position():
    # an intraday 'adjust' on a position already entered earlier -> re-price its live legs
    verdicts = [{"date": "2026-06-04", "symbol": "AAA", "verdict": "adjust", "target": 30.0, "stop": 25.0}]
    positions = [{"symbol": "AAA", "qty": 10.0}]
    plan = ap.plan_reprices(verdicts, positions, {"2026-06-04:AAA:open"})
    assert plan == [{"key": "2026-06-04:AAA:adjust:30.0:25.0", "symbol": "AAA",
                     "qty": 10, "target": 30.0, "stop": 25.0}]


def test_plan_reprices_carried_position_without_open_key():
    # a position carried from a prior day (open intent cleared by the reset) still re-prices on adjust
    verdicts = [{"date": "2026-06-04", "symbol": "AAA", "verdict": "adjust", "target": 30.0, "stop": 25.0}]
    positions = [{"symbol": "AAA", "qty": 10.0}]
    plan = ap.plan_reprices(verdicts, positions, set())
    assert plan == [{"key": "2026-06-04:AAA:adjust:30.0:25.0", "symbol": "AAA",
                     "qty": 10, "target": 30.0, "stop": 25.0}]


def test_plan_reprices_skips_symbol_opened_this_cycle():
    # a fresh entry this cycle already has its bracket at the new levels -> no re-price
    verdicts = [{"date": "2026-06-04", "symbol": "AAA", "verdict": "adjust", "target": 30.0, "stop": 25.0}]
    positions = [{"symbol": "AAA", "qty": 10.0}]
    assert ap.plan_reprices(verdicts, positions, set(), skip_symbols={"AAA"}) == []


def test_plan_reprices_idempotent_and_filters():
    verdicts = [
        {"date": "2026-06-04", "symbol": "AAA", "verdict": "adjust", "target": 30.0, "stop": 25.0},   # already done
        {"date": "2026-06-04", "symbol": "BBB", "verdict": "reaffirm", "target": 30.0, "stop": 25.0}, # not an adjust
        {"date": "2026-06-04", "symbol": "CCC", "verdict": "adjust", "target": 30.0, "stop": 25.0},   # not held
        {"date": "2026-06-04", "symbol": "DDD", "verdict": "adjust", "target": 30.0, "stop": 25.0},   # opened this cycle
    ]
    positions = [{"symbol": "AAA", "qty": 10.0}, {"symbol": "BBB", "qty": 5.0}, {"symbol": "DDD", "qty": 4.0}]
    done = {"2026-06-04:AAA:open", "2026-06-04:AAA:adjust:30.0:25.0", "2026-06-04:DDD:open"}
    assert ap.plan_reprices(verdicts, positions, done, skip_symbols={"DDD"}) == []


def test_sync_reprices_on_intraday_adjust(tmp_path, monkeypatch):
    verdicts = [{"date": "2026-06-04", "symbol": "AAA", "verdict": "adjust", "target": 30.0, "stop": 25.0}]
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    (tmp_path / "exec.json").write_text(json.dumps(["2026-06-04:AAA:open"]))  # entered on an earlier cycle
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    bd = tmp_path / "bridge"; bd.mkdir()
    (bd / "2026-06-04T1030.md").write_text("### [[AAA]]\n- Target: $40.0 (+1%) | Stop: $20.0 (-1%)\n")
    monkeypatch.setattr(ap, "BRIDGE_DIR", bd)
    b = FakeBroker(positions=[{"symbol": "AAA", "qty": 10.0}],
                   orders=[{"symbol": "AAA", "side": "sell", "id": "old"}])
    r = ap.sync(broker=b)
    assert r["repriced"] == 1
    assert b.reprices == [("AAA", 10, 30.0, 25.0)]  # Tony's adjust levels, not the scanner's 40/20


def test_notify_closed_alerts_but_no_longer_writes_ledger(tmp_path, monkeypatch):
    # New contract: _notify_closed fires the exit ALERT, but the realized LEDGER is now rebuilt
    # authoritatively from Alpaca fills (reconcile_realized) — so it no longer writes un-id'd rows.
    from runner.ledger import tony_realized as tr
    import runner.tools.notify as nf
    monkeypatch.setattr(ap, "NOTIFY_STATE", tmp_path / "notify.json")
    monkeypatch.setattr(tr, "REALIZED_FILE", tmp_path / "realized.json")
    monkeypatch.setattr(ap, "BRIDGE_DIR", tmp_path / "nobridge")
    (tmp_path / "notify.json").write_text(json.dumps(
        [{"symbol": "AAA", "qty": 10.0, "avg_entry_price": 20.0}]))
    calls = []
    monkeypatch.setattr(nf, "notify_exit",
                        lambda *a, **k: calls.append((a, k)) or {"sent": True})

    class ExitBroker(FakeBroker):
        def _latest_price(self, symbol):
            return 30.0

    ap._notify_closed(ExitBroker(positions=[]))  # AAA gone -> closed
    assert len(calls) == 1 and calls[0][0][0] == "AAA"      # alert fired for AAA
    assert not (tmp_path / "realized.json").exists()        # ledger NOT written here anymore


def test_sync_skips_buy_when_market_closed(tmp_path, monkeypatch):
    # Component A gate: a closed-market buy must NOT submit, NOT enter `done`, NOT alert.
    monkeypatch.setenv("TONY_MARKET_SESSION", "closed")
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "override", "target": 30, "stop": 25}]
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    alerts = []
    monkeypatch.setattr(ap, "_notify_entry_safe", lambda *a, **k: alerts.append(a))
    b = FakeBroker()
    r = ap.sync(broker=b)
    assert b.buys == []                     # not submitted
    assert r["executed"] == 0
    assert alerts == []                     # no entry alert
    assert json.load(open(tmp_path / "exec.json")) == []   # key NOT added to done


def test_sync_closed_market_still_protects_and_closes(tmp_path, monkeypatch):
    # close / reprice / protect must keep running while the market is closed.
    monkeypatch.setenv("TONY_MARKET_SESSION", "closed")
    verdicts = [{"date": "2026-06-03", "symbol": "DDD", "verdict": "close"}]
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    bd = tmp_path / "bridge"; bd.mkdir()
    (bd / "2026-06-03T1530.md").write_text("### [[CVS]]\n- Target: $98.06 (+1%) | Stop: $88.73 (-1%)\n")
    monkeypatch.setattr(ap, "BRIDGE_DIR", bd)
    b = FakeBroker(positions=[{"symbol": "CVS", "qty": 10.0}], orders=[])
    r = ap.sync(broker=b)
    assert b.closes == ["DDD"]              # close still fires when closed
    assert r["protected"] == 1             # protection still reconciles when closed


def test_sync_buy_executes_when_market_open(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_MARKET_SESSION", "open")
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "override", "target": 30, "stop": 25}]
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    b = FakeBroker()
    r = ap.sync(broker=b)
    assert b.buys[0][0] == "AAA" and r["executed"] == 1
    assert json.load(open(tmp_path / "exec.json")) == ["2026-06-03:AAA:open"]


def test_flush_session_no_keys_still_clears(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    (tmp_path / "exec.json").write_text("[]")
    (tmp_path / "v.json").write_text("[]")
    res = ap.flush_session()
    assert res["cancelled"] == "no_keys" and "v.json" in res["cleared"]
