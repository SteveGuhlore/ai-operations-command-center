"""drawdown_breaker — code-enforced circuit breaker for Tony Stocks (T1.3).

Friday 2026-06-06: FCX, SLB, SNAP, DVN printed 4 consecutive stop-outs (~-$945 total).
No guard existed to halt new entries after that cluster. This module is that guard.

It is intentionally LLM-free and IO-free in its core logic — pure functions that operate
on the realized ledger rows already recorded by tony_realized.py. Call `current_breaker()`
for a live reading; embed `breaker_state()` in any entry-gate that already has the data.
"""
import json
import logging
import math
import os
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_DEFAULT_MAX_CONSEC = 3
_DEFAULT_MAX_DD_PCT = 8.0
_DEFAULT_THROTTLE_MULT = 0.5


# ---------------------------------------------------------------------------
# Pure logic
# ---------------------------------------------------------------------------

def consecutive_losses(rows: list) -> int:
    """Trailing run of losing trades (realized_pl < 0) from the chronological END of rows.

    Sorts by (date, exit_order_id or symbol) for a stable ordering, then counts
    backwards until a win or break-even (realized_pl >= 0) is found.
    """
    if not rows:
        return 0
    sorted_rows = sorted(
        rows,
        key=lambda r: (str(r.get("date", "")), str(r.get("exit_order_id") or r.get("symbol", ""))),
    )
    count = 0
    for row in reversed(sorted_rows):
        try:
            pl = float(row.get("realized_pl", 0) or 0)
        except (TypeError, ValueError):
            pl = 0.0
        if pl < 0:
            count += 1
        else:
            break
    return count


def max_drawdown_pct(equity_series: list) -> float:
    """Largest peak-to-trough % decline over the equity series (returned as a positive number).

    Returns 0.0 for empty series or a series with fewer than 2 points.
    Example: [100, 110, 90, 95] -> (110-90)/110*100 = 18.18...
    """
    if len(equity_series) < 2:
        return 0.0
    peak = equity_series[0]
    max_dd = 0.0
    for val in equity_series[1:]:
        if val > peak:
            peak = val
        elif peak > 0:
            dd = (peak - val) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
    return max_dd


def breaker_state(
    rows: list,
    equity_series: "list[float] | None" = None,
    *,
    max_consec: "int | None" = None,
    max_dd_pct: "float | None" = None,
    throttle_mult: "float | None" = None,
    state_known: bool = True,
) -> dict:
    """Compute the circuit-breaker state from realized rows and an optional equity series.

    Returns:
        {
            "halted": bool,           # True -> no new entries (throttle_mult=0.0)
            "throttle_mult": float,   # 0.0 halted / configured value soft / 1.0 clear
            "consecutive_losses": int,
            "drawdown_pct": float,    # always >= 0
            "reasons": list[str],
        }

    Config priority: explicit kwarg > env var > built-in default.
    Env vars: TONY_BREAKER_MAX_CONSEC_LOSSES, TONY_BREAKER_MAX_DRAWDOWN_PCT,
              TONY_BREAKER_THROTTLE_MULT.
    """
    cfg_max_consec = max_consec if max_consec is not None else int(
        os.environ.get("TONY_BREAKER_MAX_CONSEC_LOSSES", str(_DEFAULT_MAX_CONSEC))
    )
    cfg_max_dd = max_dd_pct if max_dd_pct is not None else float(
        os.environ.get("TONY_BREAKER_MAX_DRAWDOWN_PCT", str(_DEFAULT_MAX_DD_PCT))
    )
    cfg_throttle = throttle_mult if throttle_mult is not None else float(
        os.environ.get("TONY_BREAKER_THROTTLE_MULT", str(_DEFAULT_THROTTLE_MULT))
    )

    consec = consecutive_losses(rows)
    dd = max_drawdown_pct(equity_series or [])

    # Fail CLOSED when the risk state is unknown: an existing ledger/equity file that
    # cannot be read means we genuinely don't know the loss streak or drawdown, so we
    # must halt new entries rather than assume "all clear". (A *missing* file is a
    # legitimate cold start and keeps state_known=True — see current_breaker.)
    if not state_known:
        return {
            "halted": True,
            "throttle_mult": 0.0,
            "consecutive_losses": consec,
            "drawdown_pct": round(dd, 4),
            "reasons": ["risk state unknown (corrupt/unreadable ledger or equity file) — failing closed"],
        }

    halted = False
    reasons: list[str] = []

    if consec >= cfg_max_consec:
        halted = True
        reasons.append(f"consecutive_losses={consec} >= max_consec={cfg_max_consec}")

    if dd >= cfg_max_dd:
        halted = True
        reasons.append(f"drawdown={dd:.2f}% >= max_drawdown={cfg_max_dd}%")

    if halted:
        return {
            "halted": True,
            "throttle_mult": 0.0,
            "consecutive_losses": consec,
            "drawdown_pct": round(dd, 4),
            "reasons": reasons,
        }

    # Soft zone: either metric >= half the hard limit -> throttle
    soft_consec_threshold = math.ceil(cfg_max_consec / 2)
    soft_dd_threshold = cfg_max_dd / 2.0

    in_soft = False
    if consec >= soft_consec_threshold:
        in_soft = True
        reasons.append(f"soft: consecutive_losses={consec} >= {soft_consec_threshold}")
    if dd >= soft_dd_threshold:
        in_soft = True
        reasons.append(f"soft: drawdown={dd:.2f}% >= {soft_dd_threshold:.2f}%")

    return {
        "halted": False,
        "throttle_mult": cfg_throttle if in_soft else 1.0,
        "consecutive_losses": consec,
        "drawdown_pct": round(dd, 4),
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# IO (fail-soft)
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> "tuple[Any, str]":
    """Read a JSON file. Returns (data, status) where status is one of:
    'ok' (parsed), 'missing' (file absent — a clean cold start), or
    'corrupt' (exists but unreadable/invalid — risk state is UNKNOWN)."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "missing"
    except OSError as exc:
        _log.warning("drawdown_breaker: cannot read %s: %s", path, exc)
        return None, "corrupt"
    try:
        return json.loads(text), "ok"
    except json.JSONDecodeError as exc:
        _log.warning("drawdown_breaker: corrupt JSON in %s: %s", path, exc)
        return None, "corrupt"


def _realized_path() -> Path:
    return Path(os.environ.get(
        "TONY_REALIZED_FILE",
        str(Path(__file__).parent.parent.parent / "workspace" / "tony-realized.json"),
    ))


def _equity_path() -> Path:
    return Path(os.environ.get(
        "TONY_EQUITY_HISTORY_FILE",
        str(Path(__file__).parent.parent.parent / "workspace" / "equity-history.json"),
    ))


def _read_realized() -> "tuple[list, str]":
    data, status = _read_json(_realized_path())
    rows = data if (status == "ok" and isinstance(data, list)) else []
    return rows, status


def load_realized_rows() -> list:
    """Best-effort read of the Tony realized ledger. Returns [] on any error.

    Back-compat shim — prefer _read_realized() when the missing/corrupt distinction
    matters (current_breaker uses it to fail closed on corruption).
    """
    return _read_realized()[0]


def _read_equity() -> "tuple[list, str]":
    """Read workspace/equity-history.json -> (tony-equity floats, status).

    status is 'ok' | 'missing' | 'corrupt'. A malformed shape (exists but not the
    expected list-of-{tony} structure) counts as 'corrupt' so the breaker fails closed
    rather than silently reading a 0% drawdown off unreadable data.
    """
    data, status = _read_json(_equity_path())
    if status != "ok":
        return [], status
    try:
        if not isinstance(data, list):
            return [], "corrupt"
        if not data:
            return [], "ok"  # legitimately empty history (cold start)
        if not isinstance(data[0], dict) or "tony" not in data[0]:
            return [], "corrupt"
        return [float(p["tony"]) for p in data if p.get("tony") is not None], "ok"
    except (KeyError, TypeError, ValueError) as exc:
        _log.warning("drawdown_breaker: malformed equity series: %s", exc)
        return [], "corrupt"


def _load_equity_series() -> list:
    """Best-effort read of equity history. Returns [] on any error (back-compat shim)."""
    return _read_equity()[0]


def current_breaker() -> dict:
    """Convenience: breaker_state from the live realized ledger and equity history.

    Fails CLOSED (halted) when either source file exists but is corrupt/unreadable;
    a *missing* file is treated as a clean cold start (not halted).
    """
    rows, r_status = _read_realized()
    equity, e_status = _read_equity()
    state_known = "corrupt" not in (r_status, e_status)
    return breaker_state(rows, equity, state_known=state_known)
