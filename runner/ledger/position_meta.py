"""position_meta — per-position lifecycle ledger: first-seen date, high-water mark, initial risk.

The OCO bracket protects a position spatially (price levels) but the system had no TEMPORAL or
PATH state: nothing knew how long a position had been held (the <30-day swing mandate was
unenforced) or how high it had run (a +17% winner could round-trip back to its original stop if
Tony's attention was elsewhere). This ledger records, per held symbol:

    first_seen    ET trading day the position first appeared       -> max-hold time stop
    hwm           highest current_price observed across syncs      -> profit-ratchet trail
    entry         avg_entry_price at adoption
    initial_stop  the first live protective stop seen              -> R = entry - initial_stop
    horizon       "swing" (default) | "day" | "long"               -> per-horizon rules (expansion)

R (the entry->initial-stop distance) is the scanner's own volatility-calibrated risk unit for the
name, so trailing in R-multiples is volatility-aware with ZERO network calls — the Monte-Carlo
stress test showed fixed-% floors choke volatile names and ATR-style trails must scale per name.

Updated by sync() each cycle (file write only when something changed); symbols no longer held are
pruned so a re-entry restarts its clock. Fail-soft: a missing/corrupt ledger degrades to {} and
rebuilds — positions are simply re-adopted as of today.
"""

import logging
import os
from pathlib import Path

from runner.ledger._jsonio import atomic_write_json, load_dict

_log = logging.getLogger(__name__)

META_FILE = Path(
    os.environ.get(
        "TONY_POSITION_META_FILE",
        str(Path(__file__).parent.parent.parent / "workspace" / "position-meta.json"),
    )
)

# Adopted mid-flight (stop already ratcheted to/above entry, so entry-stop is meaningless) ->
# R proxy as a fraction of entry. 4% ~ a 2-ATR scanner stop on a ~2%-daily-vol swing name.
_R_PROXY_PCT = float(os.environ.get("TONY_RATCHET_R_PROXY_PCT", "4.0"))

_HORIZON_MAX_DAYS = {
    "day": 1,
    "swing": None,
}  # swing=None -> the global default; "long" is exempt


def load_meta() -> dict:
    return load_dict(META_FILE)


def save_meta(meta: dict) -> None:
    try:
        atomic_write_json(META_FILE, meta, indent=2, sort_keys=True)
    except OSError as exc:
        _log.warning("position-meta save failed: %s", exc)


def update_meta(
    meta: dict, positions: list, live_stops: dict, today: str
) -> tuple[dict, bool]:
    """Pure: fold the current sync snapshot into the ledger. Returns (new_meta, changed).
    - new symbols are adopted: first_seen=today, hwm=max(entry, px), initial_stop captured from
      the live stop leg when one exists (else left unset until protection lands);
    - held symbols ratchet their hwm up (never down);
    - symbols no longer held are pruned (re-entry restarts the clock)."""
    out = {}
    changed = False
    held_syms = set()
    for p in positions:
        sym = (p.get("symbol") or "").upper()
        try:
            qty = float(p.get("qty") or 0)
        except (TypeError, ValueError):
            continue
        if not sym or qty < 1:
            continue
        held_syms.add(sym)
        try:
            entry = float(p.get("avg_entry_price") or 0)
        except (TypeError, ValueError):
            entry = 0.0
        try:
            px = float(p.get("current_price") or 0)
        except (TypeError, ValueError):
            px = 0.0
        cur = dict(meta.get(sym) or {})
        if not cur:
            cur = {
                "first_seen": today,
                "entry": entry,
                "hwm": max(entry, px) or entry,
                "initial_stop": None,
                "horizon": "swing",
            }
            changed = True
        if px and px > float(cur.get("hwm") or 0):
            cur["hwm"] = px
            changed = True
        if cur.get("initial_stop") is None:
            stop = (live_stops.get(sym) or {}).get("stop")
            if stop is not None:
                cur["initial_stop"] = float(stop)
                changed = True
        out[sym] = cur
    if set(meta) - held_syms:
        changed = True  # something was pruned
    return out, changed


def risk_unit(m: dict) -> float | None:
    """R for a position: entry - initial_stop (the scanner's vol-calibrated risk distance).
    Falls back to a %-of-entry proxy when the captured stop is at/above entry (position adopted
    after its stop was already ratcheted) or no stop was ever captured. None when entry unknown."""
    try:
        entry = float(m.get("entry") or 0)
    except (TypeError, ValueError):
        return None
    if entry <= 0:
        return None
    stop = m.get("initial_stop")
    try:
        r = entry - float(stop) if stop is not None else 0.0
    except (TypeError, ValueError):
        r = 0.0
    if r <= 0:
        r = entry * _R_PROXY_PCT / 100.0
    return r


def horizon_max_days(m: dict, default_days: int) -> int | None:
    """Max holding days for this position's horizon. None = exempt (true long)."""
    h = (m.get("horizon") or "swing").lower()
    if h == "long":
        return None
    return _HORIZON_MAX_DAYS.get(h) or default_days
