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
from pathlib import Path

_log = logging.getLogger(__name__)

_reports = Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"
VERDICTS_FILE = Path(os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json")))
EXECUTED_LOG = Path(__file__).parent.parent.parent / "workspace" / "alpaca-executed.json"
NOTIONAL = float(os.environ.get("TONY_PAPER_NOTIONAL", "1000"))

_OPEN = {"reaffirm", "adjust", "override"}


def _load(p) -> list:
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def plan_orders(verdicts: list, already_done: set) -> list:
    """Pure: turn fresh verdicts into intended paper actions (skips ones already executed)."""
    plan = []
    for v in verdicts:
        sym = v.get("symbol")
        key = f"{v.get('date')}:{sym}"
        if not sym or key in already_done:
            continue
        verdict = v.get("verdict")
        if verdict in _OPEN:
            plan.append({"key": key, "symbol": sym, "action": "buy", "notional": NOTIONAL,
                         "target": v.get("target"), "stop": v.get("stop")})
        elif verdict == "close":
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
    except ImportError:
        _log.warning("alpaca-py not installed — paper book disabled")
        return None

    client = TradingClient(key, secret, paper=True)

    class _Broker:
        def buy(self, symbol, notional, target, stop):
            if target and stop:
                req = MarketOrderRequest(
                    symbol=symbol, notional=round(notional, 2), side=OrderSide.BUY,
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

    return _Broker()


def sync(broker=None) -> dict:
    """Execute fresh verdicts into the paper account. Returns a summary; safe no-op w/o keys."""
    if broker is None:
        broker = _alpaca_broker()
    if broker is None:
        return {"status": "no_keys", "executed": 0}

    verdicts = _load(VERDICTS_FILE)
    done = set(_load(EXECUTED_LOG))
    plan = plan_orders(verdicts, done)

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
