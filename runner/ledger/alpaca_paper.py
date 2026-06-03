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
from pathlib import Path

_log = logging.getLogger(__name__)

_reports = Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"
VERDICTS_FILE = Path(os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json")))
EXECUTED_LOG = Path(__file__).parent.parent.parent / "workspace" / "alpaca-executed.json"
BRIDGE_DIR = Path(os.environ.get("TONY_BRIDGE_DIR", str(Path(__file__).parent.parent.parent / "bridge" / "tony-stocks")))
NOTIONAL = float(os.environ.get("TONY_PAPER_NOTIONAL", "1000"))

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
    if not BRIDGE_DIR.exists():
        return {}
    files = sorted([f for f in BRIDGE_DIR.glob("*.md") if re.match(r"\d{4}-\d{2}-\d{2}$", f.stem)], reverse=True)
    if not files:
        return {}
    try:
        return parse_scanner_levels(files[0].read_text(encoding="utf-8"))
    except OSError:
        return {}


def whole_share_qty(notional: float, price: float | None) -> int:
    """Bracket orders can't be fractional (Alpaca rejects notional + bracket), so size
    them in whole shares. Floors to budget; always at least 1 share."""
    if not price or price <= 0:
        return 1
    return max(1, int(notional // price))


def _load(p) -> list:
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def plan_orders(verdicts: list, already_done: set, scanner_levels: dict | None = None) -> list:
    """Pure: turn fresh verdicts into intended paper actions (skips ones already executed).
    An open verdict with no levels of its own (a reaffirm) inherits the scanner's target/stop
    so it's still a protected bracket — never a naked long."""
    scanner_levels = scanner_levels or {}
    plan = []
    for v in verdicts:
        sym = v.get("symbol")
        verdict = v.get("verdict")
        if not sym:
            continue
        # Key by intent (…:open / …:close), not just date+symbol, so an intraday CLOSE still
        # fires after that day's earlier BUY — exit on either side, all day.
        if verdict in _OPEN:
            key = f"{v.get('date')}:{sym}:open"
            if key in already_done:
                continue
            target, stop = v.get("target"), v.get("stop")
            if not (target and stop):
                lv = scanner_levels.get(sym, {})
                target = target or lv.get("target")
                stop = stop or lv.get("stop")
            plan.append({"key": key, "symbol": sym, "action": "buy", "notional": NOTIONAL,
                         "target": target, "stop": stop})
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
        from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
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
            if target and stop:
                # Bracket orders must be whole-share qty — notional is rejected as fractional.
                qty = whole_share_qty(notional, self._latest_price(symbol))
                req = MarketOrderRequest(
                    symbol=symbol, qty=qty, side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY, order_class=OrderClass.BRACKET,
                    take_profit=TakeProfitRequest(limit_price=round(float(target), 2)),
                    stop_loss=StopLossRequest(stop_price=round(float(stop), 2)))
            else:
                req = MarketOrderRequest(symbol=symbol, notional=round(notional, 2),
                                         side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
            client.submit_order(req)

        def close(self, symbol):
            try:
                client.close_position(symbol)
            except Exception as exc:
                _log.info("close_position(%s): %s", symbol, exc)

        def account(self):
            a = client.get_account()
            positions = client.get_all_positions()
            return {
                "equity": float(a.equity),
                "last_equity": float(a.last_equity),
                "cash": float(a.cash),
                "open_positions": [
                    {"symbol": p.symbol, "qty": float(p.qty),
                     "unrealized_pl": float(p.unrealized_pl)} for p in positions
                ],
            }

        def open_orders(self):
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            ords = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=50))
            return [{
                "symbol": o.symbol,
                "side": str(o.side).rsplit(".", 1)[-1].lower(),
                "qty": float(o.qty) if o.qty else None,
                "notional": float(o.notional) if o.notional else None,
                "order_class": str(o.order_class).rsplit(".", 1)[-1].lower(),
                "status": str(o.status).rsplit(".", 1)[-1].lower(),
            } for o in ords]

    return _Broker()


def sync(broker=None) -> dict:
    """Execute fresh verdicts into the paper account. Returns a summary; safe no-op w/o keys."""
    if broker is None:
        broker = _alpaca_broker()
    if broker is None:
        return {"status": "no_keys", "executed": 0}

    verdicts = _load(VERDICTS_FILE)
    done = set(_load(EXECUTED_LOG))
    plan = plan_orders(verdicts, done, _latest_scanner_levels())

    executed = 0
    for action in plan:
        try:
            if action["action"] == "buy":
                broker.buy(action["symbol"], action["notional"], action.get("target"), action.get("stop"))
            elif action["action"] == "close":
                broker.close(action["symbol"])
            done.add(action["key"])
            executed += 1
        except Exception as exc:
            _log.warning("alpaca order failed %s: %s", action.get("symbol"), exc)

    try:
        EXECUTED_LOG.parent.mkdir(parents=True, exist_ok=True)
        EXECUTED_LOG.write_text(json.dumps(sorted(done)), encoding="utf-8")
    except OSError as exc:
        _log.warning("executed-log write failed: %s", exc)

    return {"status": "ok", "executed": executed, "planned": len(plan)}


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
