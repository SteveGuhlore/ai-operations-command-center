"""alpaca_paper — Tony Stocks' own paper book (the true head-to-head with the bot).

His verdicts become real paper orders in HIS OWN Alpaca paper account, so his record is his
account's P&L — not a join onto the bot's trades. This captures the whole point of a second
layer: when he overrides/closes, his book diverges from the bot's, and we can finally measure
whether the 2nd pass actually makes money.

PAPER ONLY. Distinct from runner/ledger/tony_live_guard.py, which gates REAL money. Degrades
to status="no_keys" when ALPACA_* env is unset, so the cycle never breaks without it.

Decision rule per verdict:
  reaffirm / adjust / override  -> open a long (bracket with target+stop when present)
  pass                          -> skip
  close                         -> close any open position in that symbol
Idempotent: each (date, symbol) verdict is executed at most once (workspace/alpaca-executed.json).
"""
import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path

_log = logging.getLogger(__name__)

_reports = Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"
VERDICTS_FILE = Path(os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json")))
EXECUTED_LOG = Path(__file__).parent.parent.parent / "workspace" / "alpaca-executed.json"
BRIDGE_DIR = Path(os.environ.get("TONY_BRIDGE_DIR", str(Path(__file__).parent.parent.parent / "bridge" / "tony-stocks")))
NOTIONAL = float(os.environ.get("TONY_PAPER_NOTIONAL", "1000"))
# Head-to-head parity with the trading bot: SAME risk-sizing formula, caps, and order mechanics
# so the only difference between the two books is the reasoning. Accounts are unequal (Tony=$1M,
# bot=$100k), so the absolute notional cap is account-scaled — Tony deploys $10k/entry (1% of his
# $1M), the bot $5k (its config) — and the head-to-head is compared on %-returns, not absolute $.
# (See docs/CONTRACTS/execution-parity.md.) The other params match the bot exactly.
RISK_PCT = float(os.environ.get("TONY_RISK_PER_TRADE_PCT", "1.0"))          # % equity risked entry->stop
MAX_NOTIONAL = float(os.environ.get("TONY_MAX_NOTIONAL_PER_POSITION", "10000"))  # $10k/entry = 1% of $1M
MAX_OPEN_POSITIONS = int(os.environ.get("TONY_MAX_OPEN_POSITIONS", "50"))
MAX_DAILY_ORDERS = int(os.environ.get("TONY_MAX_DAILY_ORDERS", "200"))

_OPEN = {"reaffirm", "adjust", "override"}
_LEVELS_RE = re.compile(r"Target:\s*\$([\d.]+).*?Stop:\s*\$([\d.]+)", re.S)


def parse_scanner_levels(md: str) -> dict:
    """Pull the scanner's per-symbol Target/Stop out of a bridge markdown so a reaffirm
    (Tony agreeing with the scanner's plan, no levels of his own) still becomes a protected
    bracket — an exit on both sides — instead of a naked long."""
    levels: dict[str, dict] = {}
    for block in re.split(r"^### \[\[", md, flags=re.M)[1:]:
        m_sym = re.match(r"([A-Z0-9.\-]+)\]\]", block)
        m_lv = _LEVELS_RE.search(block)
        if m_sym and m_lv:
            levels[m_sym.group(1)] = {"target": float(m_lv.group(1)), "stop": float(m_lv.group(2))}
    return levels


def _latest_scanner_levels() -> dict:
    """Levels from the newest bridge — daily OR intraday. Intraday bridges introduce fresh
    Tier-1 names (e.g. a midday breakout) with their own Target/Stop; reading only the morning
    daily file left those as naked notional longs, so prefer whichever bridge is newest."""
    if not BRIDGE_DIR.exists():
        return {}
    files = sorted(f for f in BRIDGE_DIR.glob("*.md") if re.match(r"\d{4}-\d{2}-\d{2}", f.stem))
    if not files:
        return {}
    try:
        return parse_scanner_levels(files[-1].read_text(encoding="utf-8"))
    except OSError:
        return {}


def positions_needing_protection(positions: list, open_orders: list, levels: dict) -> list:
    """Pure: which open positions are carrying no stop/target and should get a GTC OCO.
    A day-bracket's exit legs expire at the 16:00 close, leaving the position naked overnight;
    this finds those so sync() can re-attach protection. Protects the whole-share floor (Alpaca
    rejects stop/limit legs on fractional qty, so a 17.59-share legacy position still gets 17
    protected); skips sub-1-share slivers and any symbol without valid target>stop."""
    protected = {o.get("symbol") for o in open_orders if o.get("side") == "sell"}
    out = []
    for p in positions:
        sym = p.get("symbol")
        whole = int(float(p.get("qty", 0) or 0))  # floor — legs can only cover whole shares
        if whole < 1 or sym in protected:
            continue
        lv = levels.get(sym) or {}
        target, stop = lv.get("target"), lv.get("stop")
        if not (target and stop) or float(target) <= float(stop):
            continue
        out.append({"symbol": sym, "qty": whole,
                    "target": round(float(target), 2), "stop": round(float(stop), 2)})
    return out


def entry_orders_to_cancel(open_orders: list) -> list:
    """Pure: only unfilled BUY-side entry orders are eligible to cancel. The SELL stop/target
    legs protecting a held position must survive — cancelling those is what left positions naked."""
    return [o for o in open_orders if o.get("side") == "buy"]


def plan_reprices(verdicts: list, positions: list, already_done: set, skip_symbols=()) -> list:
    """Pure: an intraday `adjust` on a position already entered earlier should MOVE its live
    stop/target, not open more shares. Emits a re-price per held symbol whose latest verdict is
    `adjust` with new levels. Being in `positions` already proves it's an existing holding;
    `skip_symbols` excludes names opened THIS cycle (their fresh bracket already carries the new
    levels). Keyed by the levels so it fires once per distinct adjustment — including positions
    carried over from a prior day, whose open intent was cleared by the pre-open reset."""
    held = {}
    for p in positions:
        whole = int(float(p.get("qty", 0) or 0))
        if whole >= 1:
            held[p.get("symbol")] = whole
    out = []
    for v in verdicts:
        sym = v.get("symbol")
        if v.get("verdict") != "adjust" or sym in skip_symbols or sym not in held:
            continue
        target, stop = v.get("target"), v.get("stop")
        if not (target and stop) or float(target) <= float(stop):
            continue
        tp, sl = round(float(target), 2), round(float(stop), 2)
        key = f"{v.get('date')}:{sym}:adjust:{tp}:{sl}"
        if key in already_done:
            continue
        out.append({"key": key, "symbol": sym, "qty": held[sym], "target": tp, "stop": sl})
    return out


def whole_share_qty(notional: float, price: float | None) -> int:
    """Bracket orders can't be fractional (Alpaca rejects notional + bracket), so size
    them in whole shares. Floors to budget; always at least 1 share."""
    if not price or price <= 0:
        return 1
    return max(1, int(notional // price))


def risk_based_qty(equity: float, price: float | None, stop, risk_pct: float, max_notional: float) -> int:
    """Bot-parity sizing: risk a fixed % of equity from entry to stop, capped by a max notional.
    shares = floor(min(risk$ / (price-stop), max_notional / price)); always >= 1. This is what
    keeps the head-to-head fair — Tony's stop/target levels are his reasoning, but every trade
    risks the same % as the bot regardless of how tight/wide those levels are."""
    if not price or price <= 0:
        return 1
    risk_per_share = (price - float(stop)) if stop else 0
    if risk_per_share <= 0:
        return 1
    by_risk = (equity * risk_pct / 100.0) / risk_per_share
    by_cap = max_notional / price
    return max(1, int(min(by_risk, by_cap)))


def _load(p) -> list:
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def plan_orders(verdicts: list, already_done: set, scanner_levels: dict | None = None,
                held_symbols=(), max_new_buys=None) -> list:
    """Pure: turn fresh verdicts into intended paper actions (skips ones already executed).
    An open verdict with no levels of its own (a reaffirm) inherits the scanner's target/stop
    so it's still a protected bracket — never a naked long. A buy on a name already held is
    skipped (no pyramiding across days) — the reconciler keeps the existing position protected;
    a close is always allowed. `max_new_buys` caps new entries this run (portfolio / daily-order
    parity with the bot's max_open_positions and max_daily_orders)."""
    scanner_levels = scanner_levels or {}
    plan = []
    buys = 0
    for v in verdicts:
        sym = v.get("symbol")
        verdict = v.get("verdict")
        if not sym:
            continue
        # Key by intent (…:open / …:close), not just date+symbol, so an intraday CLOSE still
        # fires after that day's earlier BUY — exit on either side, all day.
        if verdict in _OPEN:
            key = f"{v.get('date')}:{sym}:open"
            if key in already_done or sym in held_symbols:
                continue
            target, stop = v.get("target"), v.get("stop")
            if not (target and stop):
                lv = scanner_levels.get(sym, {})
                target = target or lv.get("target")
                stop = stop or lv.get("stop")
            if target and stop and float(target) <= float(stop):
                continue  # degenerate bracket (Alpaca rejects target<=stop) — skip, don't retry-fail
            if max_new_buys is not None and buys >= max_new_buys:
                continue  # at the portfolio / daily-order cap — leave for a later run
            plan.append({"key": key, "symbol": sym, "action": "buy", "notional": NOTIONAL,
                         "target": target, "stop": stop})
            buys += 1
        elif verdict == "close":
            key = f"{v.get('date')}:{sym}:close"
            if key in already_done:
                continue
            plan.append({"key": key, "symbol": sym, "action": "close"})
        # pass -> no action
    return plan


def _alpaca_broker():
    """Real broker, or None if SDK/keys absent."""
    key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    if not (key and secret):
        return None
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import (MarketOrderRequest, LimitOrderRequest,
                                             TakeProfitRequest, StopLossRequest)
        from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest
    except ImportError:
        _log.warning("alpaca-py not installed — paper book disabled")
        return None

    client = TradingClient(key, secret, paper=True)
    data = StockHistoricalDataClient(key, secret)

    class _Broker:
        def _latest_price(self, symbol):
            try:
                t = data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
                return float(t[symbol].price)
            except Exception as exc:
                _log.info("latest_price(%s) failed: %s", symbol, exc)
                return None

        def buy(self, symbol, notional, target, stop):
            price = self._latest_price(symbol)
            qty = None
            if target and stop:
                # Bracket must be whole-share (fractional is rejected). Risk-based sizing matches
                # the bot's budget; GTC so the take-profit/stop-loss legs survive the 16:00 close.
                equity = float(self.account()["equity"])
                qty = risk_based_qty(equity, price, float(stop), RISK_PCT, MAX_NOTIONAL)
                req = MarketOrderRequest(
                    symbol=symbol, qty=qty, side=OrderSide.BUY,
                    time_in_force=TimeInForce.GTC, order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=round(float(target), 2)),
                    stop_loss=StopLossRequest(stop_price=round(float(stop), 2)))
            else:
                req = MarketOrderRequest(symbol=symbol, notional=round(notional, 2),
                                         side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
            client.submit_order(req)
            return {"qty": qty, "entry": price}

        def protect(self, symbol, qty, target, stop):
            """Attach a GTC OCO exit (take-profit limit + stop-loss) to an already-open position
            that lost its bracket legs at the close. OCO carries both sides so the position is
            never naked overnight."""
            tp = round(float(target), 2)
            req = LimitOrderRequest(
                symbol=symbol, qty=int(qty), side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC, order_class=OrderClass.OCO,
                limit_price=tp,
                take_profit=TakeProfitRequest(limit_price=tp),
                stop_loss=StopLossRequest(stop_price=round(float(stop), 2)))
            client.submit_order(req)

        def reprice(self, symbol, qty, target, stop):
            """Move a held position's protection to new levels: cancel its existing GTC OCO legs,
            then place a fresh OCO. Used when Tony issues an intraday `adjust`. Alpaca releases the
            cancelled legs' held qty asynchronously, so retry the new OCO until the qty frees
            (otherwise it fails 'insufficient qty' and the position is briefly left naked)."""
            for o in self.open_orders():
                if o.get("symbol") == symbol and o.get("side") == "sell":
                    try:
                        client.cancel_order_by_id(o["id"])
                    except Exception as exc:
                        _log.info("reprice cancel %s: %s", symbol, exc)
            last = None
            for _ in range(12):
                try:
                    self.protect(symbol, qty, target, stop)
                    return
                except Exception as exc:
                    last = exc
                    if "insufficient qty" in str(exc).lower() or "40310000" in str(exc):
                        time.sleep(0.5)
                        continue
                    raise
            raise last

        def close(self, symbol):
            # Cancel the GTC stop/target SELL legs first — they HOLD the shares, so a bare
            # close_position fails on held qty and the close silently no-ops (the position stays
            # open against Tony's decision). Alpaca frees the held qty asynchronously after the
            # cancel, so retry the liquidation briefly until it goes through.
            for o in self.open_orders():
                if o.get("symbol") == symbol and o.get("side") == "sell":
                    try:
                        client.cancel_order_by_id(o["id"])
                    except Exception as exc:
                        _log.info("close cancel %s: %s", symbol, exc)
            last = None
            for _ in range(12):
                try:
                    client.close_position(symbol)
                    return
                except Exception as exc:
                    last = exc
                    s = str(exc).lower()
                    if "insufficient qty" in s or "held" in s or "40310000" in s:
                        time.sleep(0.5)
                        continue
                    _log.info("close_position(%s): %s", symbol, exc)
                    return
            _log.info("close_position(%s) gave up after retries: %s", symbol, last)

        def account(self):
            a = client.get_account()
            positions = client.get_all_positions()
            return {
                "equity": float(a.equity),
                "last_equity": float(a.last_equity),
                "cash": float(a.cash),
                "open_positions": [
                    {"symbol": p.symbol, "qty": float(p.qty),
                     "unrealized_pl": float(p.unrealized_pl),
                     "avg_entry_price": float(p.avg_entry_price) if p.avg_entry_price else None,
                     "current_price": float(p.current_price) if p.current_price else None,
                     "unrealized_plpc": float(p.unrealized_plpc) if p.unrealized_plpc else None}
                    for p in positions
                ],
            }

        def open_orders(self):
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            # status=ALL (not OPEN) so an OCO's stop-loss leg — which sits in HELD, not OPEN —
            # is surfaced alongside its take-profit; otherwise the dashboard shows only the target.
            ords = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500))
            terminal = {"filled", "canceled", "cancelled", "expired", "rejected", "done_for_day", "replaced"}
            out = []
            for o in ords:
                status = str(o.status).rsplit(".", 1)[-1].lower()
                if status in terminal:
                    continue
                out.append({
                    "id": str(o.id),
                    "symbol": o.symbol,
                    "side": str(o.side).rsplit(".", 1)[-1].lower(),
                    "qty": float(o.qty) if o.qty else None,
                    "notional": float(o.notional) if o.notional else None,
                    "order_class": str(o.order_class).rsplit(".", 1)[-1].lower(),
                    "type": str(o.order_type).rsplit(".", 1)[-1].lower(),
                    "limit_price": float(o.limit_price) if o.limit_price else None,
                    "stop_price": float(o.stop_price) if o.stop_price else None,
                    "status": status,
                })
            return out

        def cancel_entry_orders(self):
            """Cancel only unfilled BUY entries; leave SELL stop/target legs guarding positions."""
            cancelled = 0
            for o in entry_orders_to_cancel(self.open_orders()):
                try:
                    client.cancel_order_by_id(o["id"])
                    cancelled += 1
                except Exception as exc:
                    _log.info("cancel entry %s: %s", o.get("symbol"), exc)
            return cancelled

    return _Broker()


NOTIFY_STATE = Path(__file__).parent.parent.parent / "workspace" / "notify-state.json"


def closed_positions(prior: list, current: list) -> list:
    """Pure: positions held last cycle but gone (or zeroed) now = closed since then."""
    cur = {p.get("symbol"): float(p.get("qty") or 0) for p in current}
    return [p for p in prior
            if float(p.get("qty") or 0) > 0 and cur.get(p.get("symbol"), 0) <= 0]


def _notify_entry_safe(symbol, qty, entry, stop, target) -> None:
    """Fire a cosmetic entry alert. Fail-soft: a notify error never touches the trading path."""
    try:
        from runner.tools.notify import notify_entry
        notify_entry(symbol, qty if qty is not None else "?", entry, stop, target, RISK_PCT)
    except Exception as exc:
        _log.info("notify entry failed: %s", exc)


def _notify_closed(broker) -> None:
    """Diff open positions vs the last cycle's snapshot; alert on any that closed (target/stop/
    Tony's close), then persist the new snapshot. Cosmetic + fail-soft — never raises."""
    try:
        current = broker.account().get("open_positions", [])
    except Exception as exc:
        _log.info("notify closed read failed: %s", exc)
        return
    for p in closed_positions(_load(NOTIFY_STATE), current):
        sym, qty, entry = p.get("symbol"), p.get("qty"), p.get("avg_entry_price")
        try:
            from runner.tools.notify import notify_exit
            last = broker._latest_price(sym)
            pnl = (float(last) - float(entry)) * float(qty) if (last and entry and qty) else 0.0
            notify_exit(sym, qty, last, round(pnl, 2))
        except Exception as exc:
            _log.info("notify exit %s failed: %s", sym, exc)
    snap = [{"symbol": p.get("symbol"), "qty": p.get("qty"),
             "avg_entry_price": p.get("avg_entry_price")} for p in current]
    try:
        NOTIFY_STATE.parent.mkdir(parents=True, exist_ok=True)
        NOTIFY_STATE.write_text(json.dumps(snap), encoding="utf-8")
    except OSError as exc:
        _log.info("notify state write failed: %s", exc)


def sync(broker=None) -> dict:
    """Execute fresh verdicts into the paper account. Returns a summary; safe no-op w/o keys."""
    if broker is None:
        broker = _alpaca_broker()
    if broker is None:
        return {"status": "no_keys", "executed": 0}

    verdicts = _load(VERDICTS_FILE)
    done = set(_load(EXECUTED_LOG))
    levels = _latest_scanner_levels()
    try:
        held = {p.get("symbol") for p in broker.account().get("open_positions", [])
                if float(p.get("qty", 0) or 0) > 0}
    except Exception as exc:
        _log.warning("held read failed: %s", exc)
        held = set()
    today = str(date.today())
    today_opens = sum(1 for k in done if isinstance(k, str) and k.startswith(today) and k.endswith(":open"))
    max_new = max(0, min(MAX_OPEN_POSITIONS - len(held), MAX_DAILY_ORDERS - today_opens))
    plan = plan_orders(verdicts, done, levels, held, max_new_buys=max_new)

    executed = 0
    opened_now = set()
    for action in plan:
        try:
            if action["action"] == "buy":
                info = broker.buy(action["symbol"], action["notional"],
                                  action.get("target"), action.get("stop")) or {}
                opened_now.add(action["symbol"])
                _notify_entry_safe(action["symbol"], info.get("qty"), info.get("entry"),
                                   action.get("stop"), action.get("target"))
            elif action["action"] == "close":
                broker.close(action["symbol"])
            done.add(action["key"])
            executed += 1
        except Exception as exc:
            _log.warning("alpaca order failed %s: %s", action.get("symbol"), exc)

    repriced = _reprice_adjusted(broker, verdicts, done, opened_now)

    try:
        EXECUTED_LOG.parent.mkdir(parents=True, exist_ok=True)
        EXECUTED_LOG.write_text(json.dumps(sorted(done)), encoding="utf-8")
    except OSError as exc:
        _log.warning("executed-log write failed: %s", exc)

    protected = _reconcile_protection(broker, levels)
    _notify_closed(broker)  # exit alerts for anything closed since last cycle (target/stop/close)

    try:  # snapshot the book so briefs can inject it without a network call (fail-soft)
        from runner.tools.tony_book import write_book_cache
        write_book_cache(broker)
    except Exception as exc:
        _log.info("book cache update skipped: %s", exc)

    return {"status": "ok", "executed": executed, "planned": len(plan),
            "repriced": repriced, "protected": protected}


def _reprice_adjusted(broker, verdicts: list, done: set, opened_now: set) -> int:
    """Move live stop/target for any held position Tony adjusted intraday (mutates `done` with the
    reprice keys so it fires once per adjustment). Skips symbols just opened this cycle — their
    fresh bracket already carries the new levels."""
    try:
        positions = broker.account().get("open_positions", [])
    except Exception as exc:
        _log.warning("reprice read failed: %s", exc)
        return 0
    count = 0
    for rp in plan_reprices(verdicts, positions, done, opened_now):
        try:
            broker.reprice(rp["symbol"], rp["qty"], rp["target"], rp["stop"])
            done.add(rp["key"])
            count += 1
            _log.info("Re-priced %s x%d to target %.2f / stop %.2f",
                      rp["symbol"], rp["qty"], rp["target"], rp["stop"])
            try:
                from runner.tools.notify import notify_reprice
                notify_reprice(rp["symbol"], rp["qty"], rp["target"], rp["stop"])
            except Exception as nexc:
                _log.info("notify reprice failed: %s", nexc)
        except Exception as exc:
            _log.warning("reprice %s failed: %s", rp["symbol"], exc)
    return count


def _reconcile_protection(broker, levels: dict) -> int:
    """Re-attach a GTC OCO exit to any whole-share position that's carrying no protective order
    (its day-bracket legs expired at the close). Best-effort: a per-symbol failure is logged and
    retried next cycle. Never touches positions that already have a working stop/target."""
    protected = 0
    try:
        positions = broker.account().get("open_positions", [])
        orders = broker.open_orders()
    except Exception as exc:
        _log.warning("protection reconcile read failed: %s", exc)
        return 0
    for need in positions_needing_protection(positions, orders, levels):
        try:
            broker.protect(need["symbol"], need["qty"], need["target"], need["stop"])
            protected += 1
            _log.info("Re-protected %s x%d (target %.2f / stop %.2f)",
                      need["symbol"], need["qty"], need["target"], need["stop"])
        except Exception as exc:
            _log.warning("protect %s failed: %s", need["symbol"], exc)
    return protected


def account_record() -> dict:
    """Tony's paper P&L for the Cockpit equity curve. status=no_keys when unconfigured."""
    broker = _alpaca_broker()
    if broker is None:
        return {"status": "no_keys"}
    try:
        acct = broker.account()
        acct["status"] = "ok"
        return acct
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def paper_book() -> dict:
    """Tony's live paper book for the dashboard: account + open positions + working orders.
    Pre-open the orders are ACCEPTED/working and positions are empty; intraday they fill into
    positions. Degrades to status=no_keys so the dashboard never breaks."""
    broker = _alpaca_broker()
    if broker is None:
        return {"status": "no_keys", "open_positions": [], "orders": []}
    try:
        acct = broker.account()
        acct["orders"] = broker.open_orders()
        acct["status"] = "ok"
        return acct
    except Exception as exc:
        return {"status": "error", "error": str(exc), "open_positions": [], "orders": []}


def flush_session(broker=None) -> dict:
    """Pre-open reset so each market day (and any overnight test data) starts on a clean book:
    cancel UNFILLED entry orders, forget executions, and empty the verdicts file. PAPER ONLY —
    cancels only pending entries, never closes filled positions NOR their protective stop/target
    legs (those guard overnight holds). Safe if keys are absent."""
    if broker is None:
        broker = _alpaca_broker()
    cancelled = "no_keys"
    if broker is not None:
        try:
            broker.cancel_entry_orders()
            cancelled = "ok"
        except Exception as exc:
            cancelled = f"error: {exc}"
    cleared = []
    for f in (EXECUTED_LOG, VERDICTS_FILE):
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("[]", encoding="utf-8")
            cleared.append(f.name)
        except OSError as exc:
            _log.warning("flush_session: clearing %s failed: %s", f, exc)
    return {"cancelled": cancelled, "cleared": cleared}
