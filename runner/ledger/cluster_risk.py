"""T1.9 — Portfolio cluster/sector correlation cap.

Motivating incident: an energy cluster (FCX, SLB, DVN, energy ETFs) all held simultaneously
stopped out in a single gap-down, causing outsized single-event drawdown. This module identifies
correlation clusters and blocks NEW buys that would push any cluster past the configured cap,
preventing a repeat.

Public API
----------
cluster_of(symbol)           -> str   cluster name for ticker
cluster_counts(held)         -> dict  {cluster: count} for active (qty>0) positions
over_cluster_cap(held, sym)  -> bool  True if adding sym exceeds the per-cluster cap
filter_new_buys(plan, held)  -> (allowed, blocked)  filter a plan list by cluster cap
"""
import logging
import os

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static ticker -> cluster map
# Clusters are intentionally coarse: they reflect real correlation risk in
# the portfolio, NOT strict GICS sector assignments.
# ---------------------------------------------------------------------------

# FCX is a copper miner (materials) but it trades tightly with the energy/commodity
# complex — oil, gas, and copper move together in macro risk-off events, which is
# exactly what caused the incident. We map FCX to "energy" so the cap treats it as
# part of that correlated group.
_TICKER_CLUSTER: dict[str, str] = {
    # --- Energy / commodity complex ---
    "FCX": "energy",   # copper/materials but moves with commodity complex (see module docstring)
    "SLB": "energy",
    "DVN": "energy",
    "XOM": "energy",
    "CVX": "energy",
    "OXY": "energy",
    "HAL": "energy",
    "COP": "energy",
    "XLE": "energy",
    # --- Technology ---
    "AAPL": "tech",
    "MSFT": "tech",
    "NVDA": "tech",
    "CRM":  "tech",
    "SNAP": "tech",
    "META": "tech",
    "GOOGL":"tech",
    "AMD":  "tech",
    "XLK":  "tech",
    # --- Financials ---
    "JPM": "financials",
    "BAC": "financials",
    "GS":  "financials",
    "WFC": "financials",
    "XLF": "financials",
    # --- Healthcare ---
    "UNH": "healthcare",
    "JNJ": "healthcare",
    "PFE": "healthcare",
    "XLV": "healthcare",
    # --- Materials ---
    "NEM": "materials",
    "DD":  "materials",
    "LIN": "materials",
    # --- Consumer ---
    "AMZN": "consumer",
    "WMT":  "consumer",
    "COST": "consumer",
    "TGT":  "consumer",
    "MCD":  "consumer",
    # --- Industrials ---
    "CAT": "industrials",
    "DE":  "industrials",
    "GE":  "industrials",
    "BA":  "industrials",
    "UPS": "industrials",
    "HON": "industrials",
    # --- Broad ETFs ---
    "SPY": "etf_broad",
    "QQQ": "etf_broad",
    "IWM": "etf_broad",
    "DIA": "etf_broad",
}


def cluster_of(symbol: str) -> str:
    """Return the coarse correlation cluster name for a ticker symbol.

    Unknown symbols return "other". Input is case-insensitive. None / non-str
    inputs also return "other" rather than raising.
    """
    if not isinstance(symbol, str):
        return "other"
    return _TICKER_CLUSTER.get(symbol.upper(), "other")


# ---------------------------------------------------------------------------
# cluster_counts
# ---------------------------------------------------------------------------

def cluster_counts(held: list) -> dict:
    """Return {cluster: count} for all active (qty > 0) held positions.

    "other" symbols are intentionally NOT pooled under a shared "other" key.
    Two unknown tickers are almost certainly uncorrelated with each other, so
    treating them as a cluster would incorrectly block unrelated buys. Instead
    we simply omit "other" from the returned dict — callers that check for
    "other" cap hits will find no entry and allow the trade.
    """
    counts: dict[str, int] = {}
    for pos in held:
        qty = pos.get("qty", 0)
        if qty <= 0:
            continue
        cluster = cluster_of(pos.get("symbol"))
        if cluster == "other":
            # "other" symbols do not form a correlated group — leave uncounted
            continue
        counts[cluster] = counts.get(cluster, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# over_cluster_cap
# ---------------------------------------------------------------------------

def _default_cap() -> int:
    """Read TONY_MAX_PER_CLUSTER from env; default 3 if unset or unparseable."""
    raw = os.environ.get("TONY_MAX_PER_CLUSTER", "3")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 3


def over_cluster_cap(
    held: list,
    new_symbol: str,
    max_per_cluster: int | None = None,
) -> bool:
    """Return True if adding new_symbol to held would exceed the per-cluster cap.

    "other" symbols are never considered over cap.
    max_per_cluster kwarg overrides TONY_MAX_PER_CLUSTER env var (default 3).
    Cap is read at call time so env changes take effect without restart.
    """
    cluster = cluster_of(new_symbol)
    if cluster == "other":
        return False

    cap = max_per_cluster if max_per_cluster is not None else _default_cap()
    counts = cluster_counts(held)
    current = counts.get(cluster, 0)
    would_be = current + 1
    result = would_be > cap
    if result:
        _log.debug(
            "cluster_cap: %s cluster=%s current=%d cap=%d -> BLOCKED",
            new_symbol, cluster, current, cap,
        )
    return result


# ---------------------------------------------------------------------------
# filter_new_buys
# ---------------------------------------------------------------------------

def filter_new_buys(
    plan: list,
    held: list,
    max_per_cluster: int | None = None,
) -> tuple[list, list]:
    """Filter a plan list by the per-cluster cap, returning (allowed, blocked).

    Rules:
    - Only items with action == "buy" are subject to the cap check.
    - Non-buy items (close, adjust, …) always pass through to allowed untouched.
    - Allowed buys are simulated as added to the held book in order, so the cap
      accounts for buys approved earlier in the same plan run.
    - Blocked items receive a "blocked_reason" key (added to a copy; original
      dict is not mutated).
    - Pure; no IO.
    """
    cap = max_per_cluster if max_per_cluster is not None else _default_cap()

    # Work with a mutable copy of held so we can simulate intra-plan additions
    simulated_held = list(held)

    allowed: list = []
    blocked: list = []

    for item in plan:
        if item.get("action") != "buy":
            allowed.append(item)
            continue

        symbol = item.get("symbol", "")
        if over_cluster_cap(simulated_held, symbol, max_per_cluster=cap):
            cluster = cluster_of(symbol)
            blocked_item = {**item, "blocked_reason": f"cluster_cap:{cluster}({cap})"}
            blocked.append(blocked_item)
            _log.info("filter_new_buys: blocked %s (%s)", symbol, blocked_item["blocked_reason"])
        else:
            allowed.append(item)
            # Simulate this buy as now held so subsequent plan items see updated counts
            simulated_held.append({"symbol": symbol, "qty": 1.0})

    return allowed, blocked
