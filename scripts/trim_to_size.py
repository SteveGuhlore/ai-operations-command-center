"""Trim pyramided positions back to ~1x ENTRY_NOTIONAL, then re-protect the remainder.

A missed daily pre-open flush let stacked multi-date buy verdicts for the same name fire together
at one open, pyramiding some positions to 2-4x the intended ~$10k entry. For each position whose
market value exceeds THRESHOLD x ENTRY_NOTIONAL, this sells the whole-share excess back down to
~1x and re-attaches its existing stop/target (OCO) to what remains. PAPER via the existing broker.

--dry-run is the DEFAULT (prints the plan, changes nothing). Pass --execute to actually trim.
A name whose protective legs have no stop/target is SKIPPED (we won't leave a remainder naked).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")  # explicit path so cwd doesn't matter

from runner.ledger.alpaca_paper import _alpaca_broker, ENTRY_NOTIONAL


def _legs(orders: list, symbol: str):
    """The live protective target/stop on a symbol's SELL legs (None if missing)."""
    tgt = stop = None
    for o in orders:
        if o.get("symbol") == symbol and o.get("side") == "sell":
            if o.get("limit_price") is not None:
                tgt = float(o["limit_price"])
            if o.get("stop_price") is not None:
                stop = float(o["stop_price"])
    return tgt, stop


def build_plan(positions: list, orders: list, broker, threshold: float) -> list:
    """Pure-ish: which positions to trim and by how much. Skips anything at/below threshold."""
    plan = []
    for p in positions:
        sym = p.get("symbol")
        qty = float(p.get("qty") or 0)
        price = p.get("current_price") or broker._latest_price(sym)
        if not price or float(price) <= 0:
            print(f"  skip {sym}: no live price")
            continue
        price = float(price)
        mktval = qty * price
        if mktval <= threshold * ENTRY_NOTIONAL:
            continue
        target_qty = int(ENTRY_NOTIONAL / price)   # ~$10k in whole shares
        excess = int(qty) - target_qty
        if excess < 1:
            continue
        tgt, stop = _legs(orders, sym)
        plan.append((sym, qty, price, mktval, target_qty, excess, tgt, stop))
    return plan


def main() -> None:
    ap = argparse.ArgumentParser(description="Trim pyramided positions back to ~1x ENTRY_NOTIONAL.")
    ap.add_argument("--execute", action="store_true",
                    help="actually trim (default: dry-run, changes nothing)")
    ap.add_argument("--dry-run", action="store_true",
                    help="explicit no-op — dry-run is already the default unless --execute is given")
    ap.add_argument("--threshold", type=float, default=1.4,
                    help="only trim positions worth more than this x ENTRY_NOTIONAL (default 1.4)")
    args = ap.parse_args()

    broker = _alpaca_broker()
    if broker is None:
        print("trim_to_size: no Alpaca keys — abort.")
        return

    acct = broker.account()
    orders = broker.open_orders()
    plan = build_plan(acct.get("open_positions", []), orders, broker, args.threshold)

    if not plan:
        print(f"trim_to_size: nothing exceeds {args.threshold:g}x ENTRY_NOTIONAL "
              f"(${ENTRY_NOTIONAL:,.0f}). Book is in line.")
        return

    print(f"{'SYM':<6}{'qty':>10}{'price':>9}{'$value':>12}{'->target':>9}{'sell':>7}  tgt/stop")
    total = 0.0
    for sym, qty, price, mv, tq, ex, tgt, stop in plan:
        total += ex * price
        flag = "" if (tgt and stop) else "   <-- NO LEVELS: will SKIP (won't leave it naked)"
        print(f"{sym:<6}{qty:>10.2f}{price:>9.2f}{mv:>12,.0f}{tq:>9d}{ex:>7d}  {tgt}/{stop}{flag}")
    print(f"\n{len(plan)} position(s), ~${total:,.0f} to sell back toward ~1x.")

    if not args.execute:
        print("[dry-run] nothing changed. Re-run with --execute to trim.")
        return

    for sym, qty, price, mv, tq, ex, tgt, stop in plan:
        if not (tgt and stop):
            print(f"  SKIP {sym}: legs have no stop/target — not trimming (would leave a naked remainder).")
            continue
        try:
            broker.reduce(sym, ex)                 # cancel legs + market-sell the excess
            broker.protect(sym, tq, tgt, stop)     # re-OCO the remainder at its existing levels
            print(f"  trimmed {sym}: sold {ex} (~${ex * price:,.0f}), re-protected {tq} @ "
                  f"tgt {tgt} / stop {stop}")
        except Exception as exc:
            print(f"  FAILED {sym}: {exc}")


if __name__ == "__main__":
    main()
