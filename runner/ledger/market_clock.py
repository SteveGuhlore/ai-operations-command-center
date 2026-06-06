"""market_clock — is the US equity market open right now?

`market_session()` is the single source of truth for the execution gate (block entries when
closed) and the off-hours research orchestrator. Authoritative via Alpaca's clock; fail-safe to
a pure Eastern-time RTH check (Mon-Fri 09:30-16:00, minus a best-effort holiday set) when the
API is unavailable. Result is cached briefly so each cycle doesn't hammer the clock endpoint.

Env override `TONY_MARKET_SESSION` ("open"/"closed") wins first — for tests and manual control.
"""
import logging
import os
import time
from datetime import datetime, time as _time
from zoneinfo import ZoneInfo

_log = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")
_cache = {"value": None, "ts": 0.0}
_CACHE_TTL = 60.0

_OPEN = _time(9, 30)
_CLOSE = _time(16, 0)

# Best-effort 2026 US equity market holidays (full closures). Half-days are treated as open;
# the gate only blocks brand-new entries, so erring open on a half-day is harmless.
_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Jr. Day
    "2026-02-16",  # Washington's Birthday
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}


def _is_rth(now: datetime | None = None) -> bool:
    """Pure Eastern-time regular-trading-hours check: weekday, 09:30 <= t < 16:00, not a holiday."""
    if now is None:
        now = datetime.now(_ET)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    now = now.astimezone(_ET)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    if now.strftime("%Y-%m-%d") in _HOLIDAYS_2026:
        return False
    return _OPEN <= now.timetz().replace(tzinfo=None) < _CLOSE


def _alpaca_clock_open() -> bool | None:
    """True/False from Alpaca's clock, or None when keys/SDK are absent or the call fails."""
    key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    if not (key and secret):
        return None
    try:
        from alpaca.trading.client import TradingClient
        clock = TradingClient(key, secret, paper=True).get_clock()
        return bool(clock.is_open)
    except Exception as exc:
        _log.info("alpaca clock unavailable, using ET fail-safe: %s", exc)
        return None


def market_session(now: datetime | None = None) -> str:
    """Return "open" or "closed". Override > cache > Alpaca clock > ET fail-safe."""
    override = os.environ.get("TONY_MARKET_SESSION", "").strip().lower()
    if override in ("open", "closed"):
        return override

    nowts = time.time()
    if _cache["value"] is not None and (nowts - _cache["ts"]) < _CACHE_TTL:
        return _cache["value"]

    is_open = _alpaca_clock_open()
    if is_open is None:
        is_open = _is_rth(now)
    value = "open" if is_open else "closed"
    _cache["value"] = value
    _cache["ts"] = nowts
    return value
