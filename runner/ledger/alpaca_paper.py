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
# Fixed-notional entry sizing: every entry deploys ENTRY_NOTIONAL (~$10k = 1% of Tony's $1M book),
# in whole shares, regardless of stop width — an equal-weight book by entry size. This departs from
# the old risk-per-trade parity with the bot (which fixed RISK at 1%); now SIZE is fixed and per-trade
# risk varies with the stop distance. RISK_PCT is retained only as the conviction-scaling base
# (B1, default off). See docs/CONTRACTS/execution-parity.md.
ENTRY_NOTIONAL = float(os.environ.get("TONY_ENTRY_NOTIONAL", "10000"))      # $/entry (1% of $1M)
RISK_PCT = float(os.environ.get("TONY_RISK_PER_TRADE_PCT", "1.0"))          # conviction-scaling base (B1)
MAX_NOTIONAL = float(os.environ.get("TONY_MAX_NOTIONAL_PER_POSITION", "10000"))  # legacy cap (risk_based_qty)
MAX_OPEN_POSITIONS = int(os.environ.get("TONY_MAX_OPEN_POSITIONS", "50"))
MAX_DAILY_ORDERS = int(os.environ.get("TONY_MAX_DAILY_ORDERS", "200"))

_OPEN = {"reaffirm", "adjust", "override"}
_LEVELS_RE = re.compile(r"Target:\s*\$([\d.]+).*?Stop:\s*\$([\d.]+)", re.S)


def conviction_multiplier(confidence) -> float:
    """B1: map a verdict's confidence to a risk-budget multiplier (read at call time so it's
    test-overridable). Unknown/missing -> 1.0 (today's flat sizing). The cap in risk_based_qty
    still binds, so a high-conviction trade can never exceed MAX_NOTIONAL_PER_POSITION."""
    mults = {
        "low": float(os.environ.get("TONY_CONV_MULT_LOW", "0.5")),
        "medium": float(os.environ.get("TONY_CONV_MULT_MEDIUM", "1.0")),
        "high": float(os.environ.get("TONY_CONV_MULT_HIGH", "1.5")),
    }
    return mults.get((confidence or "").strip().lower(), 1.0)


def conviction_enabled() -> bool:
    """B1 gate. off (default) -> flat 1% sizing, B1 inert. on -> always apply the curve. auto ->
    apply only once Tony's record PROVES calibration: enough graded picks AND high-confidence
    win-rate beats low by a margin. Fail-safe to False on any error so sizing never breaks."""
    mode = os.environ.get("TONY_CONVICTION_SIZING", "off").strip().lower()
    if mode == "on":
        return True
    if mode != "auto":
        return False
    try:
        from runner.ledger.tony_scorecard import compute_record
        rec = compute_record()
    except Exception as exc:
        _log.info("conviction gate: record unavailable: %s", exc)
        return False
    if int(rec.get("graded", 0) or 0) < int(os.environ.get("TONY_CONV_MIN_GRADED", "20")):
        return False
    cal = rec.get("calibration") or {}
    hi, lo = cal.get("high"), cal.get("low")
    if hi is None or lo is None:
        return False
    return (float(hi) - float(lo)) >= float(os.environ.get("TONY_CONV_MIN_CAL_GAP", "10.0"))


def parse_scanner_levels(md: str) -> dict:
    """Pull the scanner's per-symbol Target/Stop out of a bridge markdown so a reaffirm
    (Tony agreeing with the scanner's plan, no levels of his own) still becomes a protected
    bracket — an exit on both sides — instead of a naked long."""
    levels: dict[str, dict] = {}
    for block in re.split(r"^### \[\[", md, flags=re.M)[1:]:
        m_sym = re.match(r"([A-Z0-9.\-]+)\]\]", block)
        m_lv = _LEVELS_RE.search(block)
        if m_sym and m_lv:
            try:
                # [\d.]+ can capture a malformed "1.2.3" -> float() raises; skip that one block
                # rather than crash the whole sync cycle on a single bad bridge line.
                levels[m_sym.group(1)] = {"target": float(m_lv.group(1)), "stop": float(m_lv.group(2))}
            except ValueError:
                continue
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


def _verdict_levels(verdicts: list) -> dict:
    """Pure: per-symbol target/stop from Tony's OWN verdicts (latest valid by date). A held
    position keeps protective levels even after the scanner stops surfacing it — without this a
    name that aged out of the bridge (e.g. SLB) has no level source and goes naked overnight."""
    out: dict[str, dict] = {}
    best_date: dict[str, str] = {}
    for v in verdicts:
        sym = v.get("symbol")
        target, stop = v.get("target"), v.get("stop")
        if not sym or not (target and stop):
            continue
        try:
            if float(target) <= float(stop):
                continue
        except (TypeError, ValueError):
            continue
        d = str(v.get("date", ""))
        if sym not in best_date or d >= best_date[sym]:
            best_date[sym] = d
            out[sym] = {"target": float(target), "stop": float(stop)}
    return out


def _merge_levels(*sources: dict) -> dict:
    """Pure: combine level dicts; later sources win. Pass the freshest (scanner) last so it
    overrides Tony's older verdict levels, while verdict-only names still fill the gaps."""
    merged: dict[str, dict] = {}
    for src in sources:
        if src:
            merged.update(src)
    return merged


def positions_needing_protection(positions: list, open_orders: list, levels: dict,
                                 fallback_pct: tuple | None = None) -> list:
    """Pure: which open positions are carrying no stop/target and should get a GTC OCO.
    A day-bracket's exit legs expire at the 16:00 close, leaving the position naked overnight;
    this finds those so sync() can re-attach protection. Protects the whole-share floor (Alpaca
    rejects stop/limit legs on fractional qty, so a 17.59-share legacy position still gets 17
    protected); skips sub-1-share slivers.

    When a whole-share position has no known levels (scanner dropped it AND no verdict),
    `fallback_pct=(stop_pct, target_pct)` derives a catastrophic bracket from the entry price so
    the position is NEVER left naked overnight. Off by default (preserves the old skip behavior);
    skips when the entry price is unknown."""
    # "Protected" means a working STOP leg covering the WHOLE-SHARE FLOOR — not just any sell
    # order. A lone take-profit (limit) with no stop is a half-bracket: the position still has
    # unlimited downside, so it must be re-protected (protect() cancels the lone TP and places a
    # full OCO). A stop whose quantity is SMALLER than the floor (stale qty after a partial fill /
    # re-add — the DVN 212-of-218 case) is also under-protected and gets a full re-OCO. A stop leg
    # that reports no qty is treated as covering (unknown ≠ proven short).
    stop_qty: dict[str, float] = {}
    stop_unknown: set = set()
    leg_levels: dict[str, dict] = {}
    for o in open_orders:
        if o.get("side") != "sell":
            continue
        sym = o.get("symbol")
        if o.get("limit_price") is not None:
            leg_levels.setdefault(sym, {})["target"] = float(o["limit_price"])
        if str(o.get("type") or "").startswith("stop"):
            if o.get("stop_price") is not None:
                leg_levels.setdefault(sym, {})["stop"] = float(o["stop_price"])
            q = o.get("qty")
            if q is None:
                stop_unknown.add(sym)
            stop_qty[sym] = stop_qty.get(sym, 0.0) + (float(q) if q is not None else 0.0)
    out = []
    for p in positions:
        sym = p.get("symbol")
        whole = int(float(p.get("qty", 0) or 0))  # floor — legs can only cover whole shares
        if whole < 1:
            continue
        if sym in stop_qty and (sym in stop_unknown or stop_qty[sym] >= whole):
            continue  # protected: a stop covers the floor (or its qty is unreported)
        lv = levels.get(sym) or {}
        target, stop = lv.get("target"), lv.get("stop")
        if not (target and stop):
            # Under-covered with no scanner/verdict levels: inherit the position's OWN current
            # leg prices so the full re-OCO keeps its existing risk line (the GLW/MCHP case).
            ll = leg_levels.get(sym) or {}
            target, stop = target or ll.get("target"), stop or ll.get("stop")
        if not (target and stop) or float(target) <= float(stop):
            if fallback_pct:
                try:
                    entry = float(p.get("avg_entry_price") or 0)
                except (TypeError, ValueError):
                    entry = 0.0
                if entry > 0:
                    stop_pct, target_pct = fallback_pct
                    out.append({"symbol": sym, "qty": whole,
                                "target": round(entry * (1 + target_pct), 2),
                                "stop": round(entry * (1 - stop_pct), 2)})
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


def entry_qty(price, mult: float = 1.0) -> int:
    """Whole-share quantity for a fixed-notional entry: ENTRY_NOTIONAL (×conviction mult) / price.
    Every entry targets the same ~$ size (1% of the $1M book) regardless of stop width. `mult` is
    the B1 conviction multiplier (1.0 when conviction sizing is off)."""
    return whole_share_qty(ENTRY_NOTIONAL * mult, price)


def _load(p) -> list:
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


# --- Phase-0 code-enforced guards (LLM-independent). All default OFF: live paper behavior is
# unchanged until the operator flips the flag. Each is fail-soft — a guard error never blocks the
# trading cycle. See docs/runbooks/tony-real-money-cutover.md for the flags. ---
def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "on", "yes")


def _audit(kind, symbol=None, **fields) -> None:
    if not _flag("TONY_DECISION_AUDIT"):
        return
    try:
        from runner.ledger.decision_audit import record_decision
        record_decision(kind, symbol, **fields)
    except Exception as exc:
        _log.info("decision audit skipped: %s", exc)


def _breaker_state_safe():
    """T1.3 drawdown circuit breaker — returns the state dict, or None when disabled/unavailable."""
    if not _flag("TONY_BREAKER_ENABLED"):
        return None
    try:
        from runner.ledger.drawdown_breaker import current_breaker
        return current_breaker()
    except Exception as exc:
        _log.info("breaker unavailable: %s", exc)
        return None


def _apply_cluster_cap(plan: list, held_symbols) -> list:
    """T1.9 portfolio cluster-risk cap — drop new buys that would over-concentrate a correlated
    cluster. No-op (returns plan unchanged) when disabled or on any error."""
    if not _flag("TONY_CLUSTER_CAP_ENABLED"):
        return plan
    try:
        from runner.ledger import cluster_risk
        held = [{"symbol": s, "qty": 1} for s in held_symbols]
        allowed, blocked = cluster_risk.filter_new_buys(plan, held)
        for b in blocked:
            _audit("cluster_block", b.get("symbol"), reason=b.get("blocked_reason"))
            _log.info("cluster cap blocked %s (%s)", b.get("symbol"), b.get("blocked_reason"))
        return allowed
    except Exception as exc:
        _log.warning("cluster cap failed: %s", exc)
        return plan


def symbols_exited_today(fills: list, today: str | None = None) -> set:
    """Symbols with a SELL fill dated today — i.e. exited this session, whether by a stop, a
    take-profit target, or a discretionary close (all three produce a sell fill). Drives the
    same-session re-entry block: once Tony is out of a name he doesn't buy it back the same day
    (he exited for a reason). Cross-day re-entry is unaffected — tomorrow is a fresh look."""
    t = today or str(date.today())
    return {f.get("symbol") for f in fills
            if (f.get("side") or "").lower() == "sell" and f.get("date") == t and f.get("symbol")}


def plan_orders(verdicts: list, already_done: set, scanner_levels: dict | None = None,
                held_symbols=(), max_new_buys=None, exited_today=()) -> list:
    """Pure: turn fresh verdicts into intended paper actions (skips ones already executed).
    An open verdict with no levels of its own (a reaffirm) inherits the scanner's target/stop
    so it's still a protected bracket — never a naked long. A buy on a name already held is
    skipped (no pyramiding across days) — the reconciler keeps the existing position protected;
    a close is always allowed. `max_new_buys` caps new entries this run (portfolio / daily-order
    parity with the bot's max_open_positions and max_daily_orders)."""
    scanner_levels = scanner_levels or {}
    plan = []
    buys = 0
    planned_buys: set[str] = set()  # at most ONE entry per symbol per run. A missed daily flush can
    # leave multiple dated buy verdicts for the same name stacked in the file; without this they all
    # fire in one sync and pyramid the position to 2-4x size (the June 2026 over-sizing). The held /
    # exited-today guards only catch names already in the book, not repeats within this same run.
    for v in verdicts:
        sym = v.get("symbol")
        verdict = v.get("verdict")
        if not sym:
            continue
        # Key by intent (…:open / …:close), not just date+symbol, so an intraday CLOSE still
        # fires after that day's earlier BUY — exit on either side, all day.
        if verdict in _OPEN:
            key = f"{v.get('date')}:{sym}:open"
            if key in already_done or sym in held_symbols or sym in planned_buys:
                continue
            if sym in exited_today:
                # Exited this session (stop / target / close) — don't buy it right back. He stepped
                # aside for a reason; re-evaluate tomorrow, not four minutes later.
                _log.info("skip open %s: exited earlier today — same-session re-entry blocked", sym)
                continue
            target, stop = v.get("target"), v.get("stop")
            if not (target and stop):
                lv = scanner_levels.get(sym, {})
                target = target or lv.get("target")
                stop = stop or lv.get("stop")
            if not (target and stop):
                # No protective levels (Tony's or the scanner's) -> never open a
                # naked, off-size position via the flat-notional fallback. Skip
                # (not marked done) so a later run can take it once levels exist.
                _log.info("skip open %s: no target/stop", sym)
                continue
            if target and stop and float(target) <= float(stop):
                continue  # degenerate bracket (Alpaca rejects target<=stop) — skip, don't retry-fail
            if max_new_buys is not None and buys >= max_new_buys:
                continue  # at the portfolio / daily-order cap — leave for a later run
            plan.append({"key": key, "symbol": sym, "action": "buy", "notional": NOTIONAL,
                         "target": target, "stop": stop, "confidence": v.get("confidence", "medium")})
            buys += 1
            planned_buys.add(sym)
        elif verdict == "close":
            key = f"{v.get('date')}:{sym}:close"
            if key in already_done:
                continue
            plan.append({"key": key, "symbol": sym, "action": "close"})
        # pass -> no action
    return plan


_ORDER_TERMINAL = {"filled", "canceled", "cancelled", "expired", "rejected", "done_for_day", "replaced"}


def _flatten_orders(raw_orders) -> list:
    """Pure: Alpaca order objects (fetched with nested=True) -> flat dicts, surfacing each OCO/
    bracket CHILD LEG as its own row. The held stop-loss of an OCO lives as a leg, not a top-level
    order, so without this it's invisible and a fully-protected position looks naked — which made
    the reconciler cancel the working OCO and re-place it every cycle (de-protecting the book).
    Recurses past terminal parents (a filled bracket entry still carries live tp/stop legs);
    terminal orders themselves are dropped. `parent_id` is informational (the owning order)."""
    out = []

    def _emit(o, parent_id):
        status = str(getattr(o, "status", "")).rsplit(".", 1)[-1].lower()
        if status not in _ORDER_TERMINAL:
            out.append({
                "id": str(getattr(o, "id", "")),
                "symbol": getattr(o, "symbol", None),
                "side": str(getattr(o, "side", "")).rsplit(".", 1)[-1].lower(),
                "qty": float(o.qty) if getattr(o, "qty", None) else None,
                "notional": float(o.notional) if getattr(o, "notional", None) else None,
                "order_class": str(getattr(o, "order_class", "")).rsplit(".", 1)[-1].lower(),
                "type": str(getattr(o, "order_type", "")).rsplit(".", 1)[-1].lower(),
                "limit_price": float(o.limit_price) if getattr(o, "limit_price", None) else None,
                "stop_price": float(o.stop_price) if getattr(o, "stop_price", None) else None,
                "status": status,
                "parent_id": parent_id,
            })
        # Always recurse, even past a TERMINAL parent: a filled bracket entry is terminal but still
        # carries LIVE take-profit/stop legs — dropping them would hide the protection (look naked).
        for leg in (getattr(o, "legs", None) or []):
            _emit(leg, str(getattr(o, "id", "")))

    for o in raw_orders:
        _emit(o, None)
    return out


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

        def buy(self, symbol, notional, target, stop, risk_pct=None):
            price = self._latest_price(symbol)
            qty = None
            rp = RISK_PCT if risk_pct is None else risk_pct
            if target and stop:
                # No live price -> defer rather than submit a token 1-share bracket on unknown
                # entry (whole_share_qty floors to 1). Raising leaves the key unmarked in sync()
                # so it retries next cycle once a price is available.
                if not price or price <= 0:
                    raise ValueError(f"no live price for {symbol}; deferring bracket entry")
                # Fixed-notional sizing: every entry ~ENTRY_NOTIONAL ($10k = 1% of the $1M book),
                # in whole shares, regardless of stop width. Bracket must be whole-share; GTC so the
                # tp/stop legs survive the 16:00 close. rp (conviction-scaled in sync) is a notional
                # multiplier, so B1 still sizes up/down by conviction when enabled (flat 1x default).
                qty = entry_qty(price, (rp / RISK_PCT) if RISK_PCT else 1.0)
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

        def _place_oco(self, symbol, qty, target, stop):
            tp = round(float(target), 2)
            req = LimitOrderRequest(
                symbol=symbol, qty=int(qty), side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC, order_class=OrderClass.OCO,
                limit_price=tp,
                take_profit=TakeProfitRequest(limit_price=tp),
                stop_loss=StopLossRequest(stop_price=round(float(stop), 2)))
            client.submit_order(req)

        def protect(self, symbol, qty, target, stop):
            """Attach a GTC OCO exit (take-profit limit + stop-loss) to an open position. FIRST
            cancels any existing sell legs — e.g. a lone take-profit with NO stop, which would
            otherwise both block a fresh OCO (oversell) AND leave the position with no downside
            protection. Alpaca frees the cancelled qty asynchronously, so retry until it places."""
            for o in self.open_orders():
                if o.get("symbol") == symbol and o.get("side") == "sell":
                    try:
                        client.cancel_order_by_id(o["id"])
                    except Exception as exc:
                        _log.info("protect cancel %s: %s", symbol, exc)
            last = None
            for _ in range(12):
                try:
                    self._place_oco(symbol, qty, target, stop)
                    return
                except Exception as exc:
                    last = exc
                    if "insufficient qty" in str(exc).lower() or "40310000" in str(exc):
                        time.sleep(0.5)
                        continue
                    raise
            if last:
                raise last

        def reprice(self, symbol, qty, target, stop):
            """Move a held position's protection to new levels (Tony's intraday `adjust`) — same
            cancel-then-replace-with-retry as protect()."""
            self.protect(symbol, qty, target, stop)

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
                    if "does not exist" in s or "not found" in s or "40410000" in s:
                        return  # already flat — the close's goal is met
                    # Real failure: raise so sync() does NOT mark the close done. Returning
                    # here used to record a silent no-op as executed, so a position could stay
                    # open against Tony's decision forever with no retry and no signal.
                    raise
            raise last  # qty never freed after retries — leave unmarked so next cycle retries

        def reduce(self, symbol, sell_qty):
            """Trim an oversized (pyramided) position: cancel its protective SELL legs — they HOLD
            the shares, so a sell would otherwise fail on held qty — then market-sell `sell_qty`
            whole shares. Re-protecting the remainder is the caller's job (or the next-cycle
            reconcile). Retries while Alpaca asynchronously frees the cancelled qty (same pattern
            as close/protect)."""
            q = int(float(sell_qty or 0))
            if q < 1:
                return
            for o in self.open_orders():
                if o.get("symbol") == symbol and o.get("side") == "sell":
                    try:
                        client.cancel_order_by_id(o["id"])
                    except Exception as exc:
                        _log.info("reduce cancel %s: %s", symbol, exc)
            last = None
            for _ in range(12):
                try:
                    client.submit_order(MarketOrderRequest(
                        symbol=symbol, qty=q, side=OrderSide.SELL, time_in_force=TimeInForce.DAY))
                    return
                except Exception as exc:
                    last = exc
                    if "insufficient qty" in str(exc).lower() or "40310000" in str(exc):
                        time.sleep(0.5)
                        continue
                    raise
            if last:
                raise last

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
            # status=OPEN (NOT ALL): ALL+limit=500 returns the 500 most-recent orders across all
            # history, so after churn the actual live OCOs (days old) get truncated out of the
            # window — open_orders() then can't see a position's stop (looks naked) OR the order to
            # cancel (cancel/replace fails 40310000). OPEN returns only live orders; nested=True
            # surfaces each OCO's HELD stop-loss leg, which _flatten_orders lifts to its own row.
            ords = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500, nested=True))
            return _flatten_orders(ords)

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

        def filled_orders(self, limit=200):
            """Read-only: Alpaca's actual filled orders as chronological fill dicts. The authoritative
            record for reconciling realized trades (captures stop-outs the live diff missed)."""
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            ords = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=limit))
            out = []
            for o in ords:
                if str(o.status).rsplit(".", 1)[-1].lower() != "filled" or not o.filled_avg_price:
                    continue
                out.append({
                    "symbol": o.symbol,
                    "side": str(o.side).rsplit(".", 1)[-1].lower(),
                    "qty": float(o.filled_qty) if o.filled_qty else 0.0,
                    "price": float(o.filled_avg_price),
                    "order_id": str(o.id),
                    "order_type": str(o.order_type).rsplit(".", 1)[-1].lower(),
                    "time": str(o.filled_at),
                    "date": str(o.filled_at)[:10],
                })
            return out

    return _Broker()


def reconcile_realized(broker=None) -> dict:
    """Rebuild Tony's realized ledger from Alpaca's authoritative fill history (FIFO-matched).
    Fail-soft: a no-keys or API error is a no-op, never raises into the cycle."""
    try:
        if broker is None:
            broker = _alpaca_broker()
        if broker is None:
            return {"status": "no_keys"}
        from runner.ledger.tony_realized import rebuild_from_fills
        # 500 (Alpaca's per-request max): the CLOSED-orders window is flooded by canceled OCO legs
        # from reprice churn, so 200 dropped the BUY entries of older holds that exited today (their
        # sells matched no entry and vanished from the ledger). 500 reaches meaningfully further back.
        res = rebuild_from_fills(broker.filled_orders(limit=500))
        res["status"] = "ok"
        return res
    except Exception as exc:
        _log.warning("reconcile realized failed: %s", exc)
        return {"status": "error", "error": str(exc)}


NOTIFY_STATE = Path(__file__).parent.parent.parent / "workspace" / "notify-state.json"


def closed_positions(prior: list, current: list) -> list:
    """Pure: positions held last cycle but gone (or zeroed) now = closed since then."""
    cur = {p.get("symbol"): float(p.get("qty") or 0) for p in current}
    return [p for p in prior
            if float(p.get("qty") or 0) > 0 and cur.get(p.get("symbol"), 0) <= 0]


def _verdict_thesis(verdicts, symbol) -> str:
    """One-line thesis from Tony's latest verdict on `symbol`, so the entry alert says WHY.
    Best-effort: empty string if none. Bounded so a long thesis never bloats the message."""
    sym = (symbol or "").upper()
    cands = [v for v in verdicts
             if (v.get("symbol") or "").upper() == sym and v.get("thesis")]
    if not cands:
        return ""
    thesis = " ".join(str(max(cands, key=lambda v: v.get("date", "")).get("thesis", "")).split())
    return thesis[:160] + ("…" if len(thesis) > 160 else "")


def _r_multiple(entry, exit_price, stop):
    """Return the trade's R-multiple ((exit-entry)/(entry-stop) for a long) or None if not computable.
    R is how many 'units of risk' the result was — a +1.8R win made 1.8× what was risked."""
    try:
        en, ex, st = float(entry), float(exit_price), float(stop)
    except (TypeError, ValueError):
        return None
    risk = en - st
    if risk <= 0:
        return None
    return round((ex - en) / risk, 2)


def _notify_entry_safe(symbol, qty, entry, stop, target, risk_pct=RISK_PCT, reason="") -> None:
    """Fire a cosmetic entry alert. Fail-soft: a notify error never touches the trading path.
    risk_pct is the EFFECTIVE (conviction-scaled) risk so the alert reflects B1 sizing."""
    try:
        from runner.tools.notify import notify_entry
        notify_entry(symbol, qty if qty is not None else "?", entry, stop, target, risk_pct, reason)
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
    levels = _latest_scanner_levels()  # best-effort prior protective levels for exit-reason inference
    unresolved = []  # closed but un-priceable this cycle: keep in the snapshot so we retry, never
    for p in closed_positions(_load(NOTIFY_STATE), current):  # losing the stop-out from the ledger
        sym, qty, entry = p.get("symbol"), p.get("qty"), p.get("avg_entry_price")
        try:
            last = broker._latest_price(sym)
        except Exception as exc:
            _log.info("exit price %s failed: %s", sym, exc)
            last = None
        if last is None:
            # No price yet — don't alert/record on a phantom fill; defer to a later cycle.
            unresolved.append(p)
            continue
        lv = levels.get(sym) or {}
        try:
            from runner.tools.notify import notify_exit
            from runner.ledger.tony_realized import infer_reason
            pnl = (float(last) - float(entry)) * float(qty) if (entry and qty) else 0.0
            reason = infer_reason(last, lv.get("target"), lv.get("stop"))
            r_mult = _r_multiple(entry, last, lv.get("stop"))
            notify_exit(sym, qty, last, round(pnl, 2), r_mult=r_mult, reason=reason)
        except Exception as exc:
            _log.info("notify exit %s failed: %s", sym, exc)
        # The realized LEDGER is now rebuilt authoritatively from Alpaca fills (reconcile_realized),
        # which captures stop-outs the live diff misses and dedups by order id — so we no longer
        # write un-id'd rows here (that path produced the bogus 'HELD' record). Alerts stay above.
    snap = [{"symbol": p.get("symbol"), "qty": p.get("qty"),
             "avg_entry_price": p.get("avg_entry_price")} for p in current + unresolved]
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
    try:
        # Wide window so a busy day's exits aren't pushed out of the fetch by other closed orders.
        exited_today = symbols_exited_today(broker.filled_orders(limit=500), today)
    except Exception as exc:
        _log.warning("re-entry cooldown read failed: %s", exc)
        exited_today = set()
    today_opens = sum(1 for k in done if isinstance(k, str) and k.startswith(today) and k.endswith(":open"))
    max_new = max(0, min(MAX_OPEN_POSITIONS - len(held), MAX_DAILY_ORDERS - today_opens))
    plan = plan_orders(verdicts, done, levels, held, max_new_buys=max_new, exited_today=exited_today)
    plan = _apply_cluster_cap(plan, held)  # T1.9 correlated-cluster cap (OFF by default)

    breaker = _breaker_state_safe()  # T1.3 drawdown circuit breaker (OFF by default)
    if breaker and breaker.get("halted"):
        _log.warning("drawdown breaker HALTED new entries: %s", breaker.get("reasons"))
        _audit("breaker", reasons=breaker.get("reasons"), state=breaker)
    conv_on = conviction_enabled()  # B1: scale risk by confidence only when the gate proves out
    # Market-hours gate (Component A): a closed-market `buy` would open on stale closed prices and
    # gap over the weekend — block entries when closed. close/reprice/protect/reconcile still run
    # (they only reduce risk and the GTC OCO legs must keep reconciling overnight).
    from runner.ledger.market_clock import market_session
    session = market_session()
    executed = 0
    opened_now = set()
    for action in plan:
        try:
            if action["action"] == "buy":
                if session == "closed":
                    continue  # do NOT submit, add to done, or alert — re-evaluated at the next open
                if breaker and breaker.get("halted"):
                    # Code-enforced halt: skip the entry (NOT marked done) so it's re-evaluated once
                    # the book stabilizes. Independent of the LLM — a model can't override the halt.
                    _audit("skip", action["symbol"], reason="breaker_halt")
                    continue
                throttle = breaker.get("throttle_mult", 1.0) if breaker else 1.0
                mult = (conviction_multiplier(action.get("confidence")) if conv_on else 1.0) * throttle
                rp = RISK_PCT * mult
                info = broker.buy(action["symbol"], action["notional"],
                                  action.get("target"), action.get("stop"), risk_pct=rp) or {}
                opened_now.add(action["symbol"])
                _audit("order", action["symbol"], action="buy", risk_pct=round(rp, 4),
                       qty=info.get("qty"), entry=info.get("entry"),
                       target=action.get("target"), stop=action.get("stop"))
                _notify_entry_safe(action["symbol"], info.get("qty"), info.get("entry"),
                                   action.get("stop"), action.get("target"), risk_pct=rp,
                                   reason=_verdict_thesis(verdicts, action["symbol"]))
            elif action["action"] == "close":
                broker.close(action["symbol"])
                _audit("order", action["symbol"], action="close")
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

    # Protect held positions from the freshest source available: Tony's verdict levels fill in any
    # name the scanner no longer surfaces (the SLB naked-overnight bug), scanner levels override
    # where present, and an entry-derived catastrophic bracket is the last-resort net.
    protect_levels = _merge_levels(_verdict_levels(verdicts), levels)
    protected = _reconcile_protection(broker, protect_levels, fallback_pct=_fallback_pcts())
    _liquidate_unprotectable_slivers(broker)  # close sub-1-share slivers that can never be bracketed (SLB)
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


def _fallback_pcts() -> tuple | None:
    """Catastrophic-stop fallback (stop_pct, target_pct) for naked positions with no scanner OR
    verdict levels — a wide net so nothing is ever naked overnight. Env-tunable; set
    TONY_FALLBACK_PROTECTION=off to disable. Defaults: 12% stop / 20% target."""
    if os.environ.get("TONY_FALLBACK_PROTECTION", "on").strip().lower() in ("0", "false", "off", "no"):
        return None
    try:
        return (float(os.environ.get("TONY_FALLBACK_STOP_PCT", "0.12")),
                float(os.environ.get("TONY_FALLBACK_TARGET_PCT", "0.20")))
    except ValueError:
        return (0.12, 0.20)


def _reconcile_protection(broker, levels: dict, fallback_pct: tuple | None = None) -> int:
    """Re-attach a GTC OCO exit to any whole-share position that's carrying no protective order
    (its day-bracket legs expired at the close, OR it aged out of the scanner). Best-effort: a
    per-symbol failure is logged and retried next cycle. Never touches positions that already have
    a working stop/target. `fallback_pct` adds an entry-derived bracket when no levels are known."""
    protected = 0
    try:
        positions = broker.account().get("open_positions", [])
        orders = broker.open_orders()
    except Exception as exc:
        _log.warning("protection reconcile read failed: %s", exc)
        return 0
    for need in positions_needing_protection(positions, orders, levels, fallback_pct=fallback_pct):
        try:
            broker.protect(need["symbol"], need["qty"], need["target"], need["stop"])
            protected += 1
            src = "scanner/verdict" if need["symbol"] in levels else "FALLBACK no-levels"
            _log.info("Re-protected %s x%d (target %.2f / stop %.2f) [%s]",
                      need["symbol"], need["qty"], need["target"], need["stop"], src)
        except Exception as exc:
            _log.warning("protect %s failed: %s", need["symbol"], exc)
    return protected


def _liquidate_unprotectable_slivers(broker) -> int:
    """A fractional position (<1 share) CANNOT carry an Alpaca stop/OCO — it can only ever be
    naked. So auto-close any sub-1-share sliver, leaving no position unprotected (the SLB case).
    Whole-share positions are never touched. Fail-soft; set TONY_LIQUIDATE_FRACTIONAL=off to disable."""
    if os.environ.get("TONY_LIQUIDATE_FRACTIONAL", "on").strip().lower() in ("0", "false", "off", "no"):
        return 0
    try:
        positions = broker.account().get("open_positions", [])
    except Exception as exc:
        _log.warning("sliver read failed: %s", exc)
        return 0
    closed = 0
    for p in positions:
        try:
            qty = float(p.get("qty", 0) or 0)
        except (TypeError, ValueError):
            continue
        if 0 < qty < 1:
            try:
                broker.close(p.get("symbol"))
                closed += 1
                _log.info("Liquidated unprotectable fractional sliver %s (%.4f sh)", p.get("symbol"), qty)
            except Exception as exc:
                _log.warning("sliver liquidation %s failed: %s", p.get("symbol"), exc)
    return closed


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
