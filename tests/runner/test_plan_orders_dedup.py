"""plan_orders must plan at most ONE buy per symbol per run — even when a missed daily flush
leaves multiple dated buy verdicts for the same name stacked in the file (the June 2026
pyramiding: stacked verdicts fired together at one open and over-sized positions 2-4x)."""
from runner.ledger.alpaca_paper import plan_orders


def _buys(plan, sym=None):
    return [a for a in plan if a["action"] == "buy" and (sym is None or a["symbol"] == sym)]


def test_one_buy_per_symbol_despite_stacked_dates():
    verdicts = [
        {"date": "2026-06-08", "symbol": "HAL", "verdict": "reaffirm", "target": 45, "stop": 38},
        {"date": "2026-06-09", "symbol": "HAL", "verdict": "override", "target": 46, "stop": 39},
        {"date": "2026-06-10", "symbol": "HAL", "verdict": "reaffirm", "target": 47, "stop": 40},
    ]
    plan = plan_orders(verdicts, already_done=set(), scanner_levels={}, held_symbols=(), max_new_buys=10)
    assert len(_buys(plan, "HAL")) == 1   # was 3 before the fix -> 3x pyramid


def test_distinct_symbols_still_each_planned():
    verdicts = [
        {"date": "2026-06-10", "symbol": "HAL", "verdict": "reaffirm", "target": 47, "stop": 40},
        {"date": "2026-06-10", "symbol": "ANET", "verdict": "override", "target": 180, "stop": 134},
    ]
    plan = plan_orders(verdicts, set(), {}, held_symbols=(), max_new_buys=10)
    assert {a["symbol"] for a in _buys(plan)} == {"HAL", "ANET"}


def test_held_symbol_still_skipped():
    verdicts = [{"date": "2026-06-10", "symbol": "HAL", "verdict": "reaffirm", "target": 47, "stop": 40}]
    plan = plan_orders(verdicts, set(), {}, held_symbols=("HAL",), max_new_buys=10)
    assert _buys(plan) == []
