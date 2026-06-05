"""tony_book — Tony's eyes on his OWN live paper book.

Tony trades a real ($1M paper) Alpaca account, yet until now he had no tool to SEE it:
his close/hold/adjust calls on live positions were inferred from the bridge + vault memory,
never from the actual position, its P&L, or its current protective stop/target. This module
fixes that blind spot three ways, all read-only / paper-only:

  * get_tony_book()            — live tool he calls while deciding (network, agent path).
  * book_block()               — a compact "Your Current Book" snapshot injected into briefs,
                                 read from a cache the cycle writes (NO network in the brief path).
  * execution_feedback_block() — "did my last calls actually fill / flatten / get rejected?",
                                 so a degenerate bracket or a close that didn't flatten is visible.

The cache (workspace/tony-book-cache.json) is written by alpaca_paper.sync() each cycle, piggy-
backing the account() call it already makes — so the brief path stays pure file reads. All blocks
degrade to "" when keys/cache are absent, so they never break brief creation.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)

_WORKSPACE = Path(__file__).parent.parent.parent / "workspace"
_reports = Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"


def _book_cache_path() -> Path:
    return Path(os.environ.get("TONY_BOOK_CACHE", str(_WORKSPACE / "tony-book-cache.json")))


def _verdicts_path() -> Path:
    return Path(os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json")))


def _executed_path() -> Path:
    return Path(os.environ.get("TONY_EXECUTED_LOG", str(_WORKSPACE / "alpaca-executed.json")))


def _load(p) -> list:
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def attach_protection(positions: list, orders: list) -> list:
    """Pure: annotate each open position with its live protective stop/target by matching the
    SELL-side OCO/bracket legs (a take-profit limit + a stop). A position with no sell legs is
    naked — surfaced as protected=False so Tony can see it."""
    legs: dict[str, dict] = {}
    for o in orders:
        if o.get("side") != "sell":
            continue
        sym = o.get("symbol")
        d = legs.setdefault(sym, {"target": None, "stop": None})
        if o.get("limit_price") is not None:
            d["target"] = float(o["limit_price"])
        if o.get("stop_price") is not None:
            d["stop"] = float(o["stop_price"])
    out = []
    for p in positions:
        sym = p.get("symbol")
        lv = legs.get(sym, {})
        out.append({
            "symbol": sym,
            "qty": float(p.get("qty") or 0),
            "avg_entry_price": p.get("avg_entry_price"),
            "current_price": p.get("current_price"),
            "unrealized_pl": p.get("unrealized_pl"),
            "unrealized_plpc": p.get("unrealized_plpc"),
            "stop": lv.get("stop"),
            "target": lv.get("target"),
            "protected": lv.get("stop") is not None or lv.get("target") is not None,
        })
    return out


def write_book_cache(broker) -> dict:
    """Snapshot the live book to the cache the briefs read. Called by sync() each cycle with the
    broker it already holds — one extra account()+open_orders() read, fail-soft. Returns the cache."""
    try:
        acct = broker.account()
        orders = broker.open_orders()
    except Exception as exc:
        _log.info("book cache snapshot failed: %s", exc)
        return {}
    cache = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "status": "ok",
        "equity": acct.get("equity"),
        "last_equity": acct.get("last_equity"),
        "cash": acct.get("cash"),
        "positions": attach_protection(acct.get("open_positions", []), orders),
    }
    try:
        p = _book_cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except OSError as exc:
        _log.info("book cache write failed: %s", exc)
    return cache


def read_book_cache() -> dict:
    try:
        return json.loads(_book_cache_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def _fmt_money(x) -> str:
    try:
        return f"${float(x):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(x) -> str:
    try:
        return f"{float(x) * 100:+.1f}%"   # alpaca unrealized_plpc is a fraction
    except (TypeError, ValueError):
        return "—"


def _fmt_price(x) -> str:
    try:
        return f"${float(x):.2f}"
    except (TypeError, ValueError):
        return "—"


def book_block(cache: dict | None = None) -> str:
    """Compact 'Your Current Book' markdown for injection into a brief. Empty string when the
    cache is missing/keyless so briefs without an Alpaca book simply omit the section."""
    cache = read_book_cache() if cache is None else cache
    if not cache or cache.get("status") != "ok":
        return ""
    positions = [p for p in cache.get("positions", []) if float(p.get("qty") or 0) > 0]
    header = (
        f"## Your Current Book (live snapshot — {cache.get('ts', '?')})\n\n"
        f"Equity {_fmt_money(cache.get('equity'))} · cash {_fmt_money(cache.get('cash'))} · "
        f"{len(positions)} open position(s). This is YOUR actual paper account — ground every "
        f"hold/close/adjust on the real position below, not on memory.\n"
    )
    if not positions:
        return header + "\n_Flat — no open positions. Decide fresh entries from the bridge._\n"
    lines = [
        "\n| Symbol | Qty | Entry | Last | Unreal P/L | P/L % | Stop | Target | Protected |",
        "|--------|-----|-------|------|------------|-------|------|--------|-----------|",
    ]
    for p in sorted(positions, key=lambda x: float(x.get("unrealized_plpc") or 0)):
        lines.append(
            f"| {p.get('symbol')} | {int(float(p.get('qty') or 0))} | "
            f"{_fmt_price(p.get('avg_entry_price'))} | {_fmt_price(p.get('current_price'))} | "
            f"{_fmt_money(p.get('unrealized_pl'))} | {_fmt_pct(p.get('unrealized_plpc'))} | "
            f"{_fmt_price(p.get('stop'))} | {_fmt_price(p.get('target'))} | "
            f"{'yes' if p.get('protected') else '⚠️ NAKED'} |"
        )
    return header + "\n".join(lines) + "\n"


_OPEN = {"reaffirm", "adjust", "override"}


def summarize_execution(verdicts: list, executed_keys: set, held: set) -> list[str]:
    """Pure: turn the current verdicts + executed-log + held symbols into short feedback lines.
    Answers 'did my last calls actually land?' — a filled bracket, a fill that already exited, a
    close that flattened, a bracket rejected for target<=stop, or one still pending at the cap."""
    out = []
    for v in verdicts:
        sym = v.get("symbol")
        verdict = (v.get("verdict") or "").lower()
        if not sym:
            continue
        if verdict in _OPEN:
            key = f"{v.get('date')}:{sym}:open"
            tgt, stop = v.get("target"), v.get("stop")
            degenerate = tgt is not None and stop is not None and float(tgt) <= float(stop)
            if key in executed_keys:
                out.append(f"✅ {sym} ({verdict}) filled — {'in your book' if sym in held else 'already exited'}.")
            elif degenerate:
                out.append(f"⚠️ {sym} ({verdict}) NOT executed — target ≤ stop ({tgt} ≤ {stop}). Fix your levels.")
            else:
                out.append(f"⏸️ {sym} ({verdict}) not executed yet — likely the open-position/daily cap; revisit.")
        elif verdict == "close":
            key = f"{v.get('date')}:{sym}:close"
            if key in executed_keys:
                flat = "flattened" if sym not in held else "⚠️ STILL HELD — close did not flatten"
                out.append(f"🔴 {sym} close executed — {flat}.")
            else:
                out.append(f"⏸️ {sym} close not executed yet.")
    return out


def execution_feedback_block() -> str:
    """Markdown feedback on whether Tony's recent verdicts actually executed. Reads the current
    verdicts + executed-log + book cache (all written by the cycle) — empty string when there's
    nothing to report so briefs stay clean before any trading has happened."""
    verdicts = _load(_verdicts_path())
    if not verdicts:
        return ""
    executed_keys = set(_load(_executed_path()))
    cache = read_book_cache()
    held = {p.get("symbol") for p in cache.get("positions", []) if float(p.get("qty") or 0) > 0}
    lines = summarize_execution(verdicts, executed_keys, held)
    if not lines:
        return ""
    return ("## Execution Feedback — did your last calls land?\n\n"
            + "\n".join(f"- {ln}" for ln in lines)
            + "\n\nIf a close shows STILL HELD or a bracket was rejected, re-issue a corrected verdict.\n")


def get_tony_book() -> dict:
    """Live read of Tony's paper book + each position's protective levels. Read-only."""
    try:
        from runner.ledger.alpaca_paper import paper_book
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    book = paper_book()
    if book.get("status") != "ok":
        return {"status": book.get("status", "error"), "positions": [], "orders": book.get("orders", [])}
    positions = attach_protection(book.get("open_positions", []), book.get("orders", []))
    return {
        "status": "ok",
        "equity": book.get("equity"),
        "cash": book.get("cash"),
        "last_equity": book.get("last_equity"),
        "positions": positions,
        "naked": [p["symbol"] for p in positions if float(p["qty"]) >= 1 and not p["protected"]],
    }


TOOL_SPEC = {
    "name": "get_tony_book",
    "description": (
        "Read YOUR OWN live paper book before deciding on any position — read-only, no side "
        "effects. Returns your equity, cash, and every open position with its quantity, average "
        "entry, current price, unrealized P/L (% and $), AND its live protective stop/target plus "
        "whether it's protected. Call this FIRST on any intraday/pre-open brief so your hold / "
        "adjust / close calls are grounded in the real position and its current risk levels — not "
        "memory. `naked` lists any whole-share position with no protective order. Example: get_tony_book()"
    ),
    "input_schema": {"type": "object", "properties": {}},
}
