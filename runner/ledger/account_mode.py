"""account_mode — the single source of truth for paper ↔ real-money execution (Phase 2).

The whole execution path is ACCOUNT-AGNOSTIC: every guard (drawdown breaker, sizing, risk limits,
cluster cap, audit log) behaves IDENTICALLY regardless of mode. Going live is therefore a pure
config swap — flip TONY_ACCOUNT_MODE to "live", supply a SEPARATE live Alpaca key pair, and clear the
existing tony_live_guard. No code is rearchitected at cutover.

Default is "paper" and `live_preconditions` is FAIL-CLOSED: it refuses unless the operator has
explicitly opted in, the track record passes the guard, AND the live account is isolated from the
bot's account (§5.3 hard rule — never trade real money from the bot's keys). This module holds NO
keys and enables nothing on its own.
"""
import os

from runner.ledger import tony_live_guard


def account_mode() -> str:
    """'paper' (default) or 'live'. Read at call time so a flag flip needs no code change."""
    mode = os.environ.get("TONY_ACCOUNT_MODE", "paper").strip().lower()
    return "live" if mode == "live" else "paper"


def is_live() -> bool:
    return account_mode() == "live"


def is_paper() -> bool:
    return not is_live()


def money_label() -> str:
    """Public-copy label. 'real' once live, 'paper' otherwise — the one switch the cutover-day
    paper-language scrub keys off so no public surface has to hardcode 'paper'."""
    return "real" if is_live() else "paper"


def live_credentials() -> tuple:
    """The SEPARATE live key pair (distinct env from the bot's ALPACA_*). Empty until the operator
    provides them on cutover day — this module never carries keys."""
    return (os.environ.get("TONY_LIVE_ALPACA_API_KEY"), os.environ.get("TONY_LIVE_ALPACA_SECRET_KEY"))


def live_preconditions(record: dict) -> dict:
    """Fail-CLOSED gate every real-money order must clear. Combines: mode==live, the existing
    tony_live_guard track-record/kill-switch gate, and ACCOUNT ISOLATION (live keys present and
    distinct from the bot's keys). Returns {ready, reasons}."""
    reasons = []
    if not is_live():
        reasons.append("TONY_ACCOUNT_MODE is not 'live' (paper by default)")

    guard = tony_live_guard.live_allowed(record or {})
    reasons.extend(guard.get("reasons", []))

    live_key, live_secret = live_credentials()
    if not (live_key and live_secret):
        reasons.append("live Alpaca credentials not provided (TONY_LIVE_ALPACA_API_KEY/SECRET)")
    elif live_key == os.environ.get("ALPACA_API_KEY") or live_secret == os.environ.get("ALPACA_SECRET_KEY"):
        # Both the key AND the secret must differ from the bot account — a reused secret
        # is just as much a cross-account leak as a reused key (§5.3).
        reasons.append("live account not isolated from the bot account (§5.3) — keys must differ")

    return {"ready": not reasons, "reasons": reasons}
