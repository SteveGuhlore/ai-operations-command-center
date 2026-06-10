"""research_queue — ranked candidate queue + open re-check gate (Component C).

The off-market wave (Component B) produces a ranked candidate queue in workspace/research-queue.json
(a SEPARATE file from the verdicts/executed-log so the 09:25 TonyPreOpenReset wipe never erases it).
At each market open, `recheck_queue` re-validates the top-N candidates against FRESH live prices,
discards any whose setup no longer holds, and writes normal execution verdicts for the survivors —
which the existing alpaca_paper.sync() executes within the existing risk caps. Stale closed-market
prices NEVER execute directly: a candidate with no live price, or whose price has breached the
proposed stop / blown past the proposed target, is dropped.
"""
import json
import logging
import os
from datetime import datetime, date
from pathlib import Path

_log = logging.getLogger(__name__)

QUEUE_FILE = Path(os.environ.get(
    "TONY_RESEARCH_QUEUE_FILE",
    str(Path(__file__).parent.parent.parent / "workspace" / "research-queue.json"),
))
# Same verdicts file alpaca_paper / tony_scorecard read, so the open re-check feeds the normal flow.
_reports = Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"
VERDICTS_FILE = Path(os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json")))

_FIELDS = ("symbol", "thesis_ref", "score", "confidence", "proposed_target", "proposed_stop", "source")


def write_queue(candidates: list, target_open: str) -> dict:
    """Persist a best-first ranked candidate queue with a generated_at + target-open header."""
    now = datetime.now().isoformat()
    rows = []
    for c in candidates:
        row = {k: c.get(k) for k in _FIELDS}
        row["generated_at"] = c.get("generated_at", now)
        rows.append(row)
    rows.sort(key=lambda r: float(r.get("score") or 0), reverse=True)
    payload = {"generated_at": now, "target_open": target_open, "candidates": rows}
    try:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        QUEUE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        _log.warning("research queue write failed: %s", exc)
    return payload


def read_queue() -> dict:
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"candidates": []}
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {"candidates": []}


def _to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def queue_research_candidate(symbol: str, score, confidence: str = "medium",
                             proposed_target=None, proposed_stop=None,
                             thesis_ref: str = "", source: str = "research_wave") -> dict:
    """Append ONE ranked candidate to workspace/research-queue.json — deterministically. The
    research-wave RANK step used to have the LLM hand-write the whole JSON file; it narrated the
    step without reliably producing it, so the queue came out empty (and triggered a Scout/Forge
    'empty research-queue' investigation loop). This tool takes the fields and persists the row
    itself: reads the queue, dedupes by symbol (latest wins), re-sorts best-first, writes it back,
    and stamps the target-open header. Call it once per candidate."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return {"error": "symbol is required"}
    sc = _to_float(score)
    if sc is None:
        return {"error": f"score must be numeric, got {score!r}"}
    try:
        from runner.bridge.research_wave import _next_open_date
        target_open = _next_open_date()
    except Exception:
        target_open = ""
    existing = read_queue()
    cands = [c for c in (existing.get("candidates") or [])
             if (c.get("symbol") or "").upper() != symbol]
    cands.append({
        "symbol": symbol, "thesis_ref": thesis_ref, "score": sc, "confidence": confidence,
        "proposed_target": _to_float(proposed_target), "proposed_stop": _to_float(proposed_stop),
        "source": source, "generated_at": datetime.now().isoformat(),
    })
    payload = write_queue(cands, existing.get("target_open") or target_open)
    return {"success": True, "symbol": symbol, "queue_size": len(payload.get("candidates", []))}


TOOL_SPEC = {
    "name": "queue_research_candidate",
    "description": (
        "Add ONE name to your ranked overnight research queue (workspace/research-queue.json) — "
        "call this once per candidate in the FINAL research-rank step instead of hand-writing the "
        "JSON file. The queue is re-validated against fresh prices at the next open and the "
        "survivors auto-execute within the risk caps, so a name only belongs here with a real "
        "proposed_target/proposed_stop. Deterministic + deduped by symbol; narrating that you "
        "'wrote the queue' without calling this means it was NOT saved. "
        "Example: queue_research_candidate(symbol='GTLB', score=82, confidence='high', "
        "proposed_target=78.5, proposed_stop=71.0, thesis_ref='4-day momentum + XLK tailwind', "
        "source='conviction_deepdive')"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker (required)."},
            "score": {"type": "number", "description": "Your 0-100 conviction for ranking (required)."},
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "proposed_target": {"type": "number", "description": "Proposed take-profit price."},
            "proposed_stop": {"type": "number", "description": "Proposed stop price."},
            "thesis_ref": {"type": "string", "description": "Short thesis / where the idea came from."},
            "source": {"type": "string", "description": "Which research step produced it, e.g. 'edge_mining'."},
        },
        "required": ["symbol", "score"],
    },
}


def _setup_holds(price, target, stop) -> bool:
    """A candidate's setup still holds only if there is a FRESH price strictly inside the
    proposed (stop, target) band — i.e. it hasn't already stopped out or run past the target."""
    if price is None:
        return False
    try:
        p = float(price)
        t = float(target)
        s = float(stop)
    except (TypeError, ValueError):
        return False
    return s < p < t


def _load_verdicts() -> list:
    try:
        data = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def recheck_queue(price_fn=None, top_n: int = 10) -> dict:
    """Open re-check gate: re-validate the top-N candidates against fresh live prices, then write
    execution verdicts for the survivors. Returns {validated, discarded}."""
    if price_fn is None:
        from runner.tools.stock_data import get_stock_data
        def price_fn(sym):  # noqa: E306
            d = get_stock_data(sym)
            return d.get("price") if isinstance(d, dict) else None

    queue = read_queue()
    candidates = (queue.get("candidates") or [])[:top_n]
    validated, discarded, new_verdicts = [], [], []
    today = str(date.today())
    for c in candidates:
        sym = c.get("symbol")
        if not sym:
            continue
        price = None
        try:
            price = price_fn(sym)
        except Exception as exc:
            _log.info("recheck price %s failed: %s", sym, exc)
        if _setup_holds(price, c.get("proposed_target"), c.get("proposed_stop")):
            new_verdicts.append({
                "date": today, "symbol": sym, "verdict": "override",
                "target": float(c.get("proposed_target")), "stop": float(c.get("proposed_stop")),
                "confidence": c.get("confidence", "medium"),
                "source": "research_queue_recheck",
            })
            validated.append(sym)
        else:
            discarded.append(sym)

    if new_verdicts:
        verdicts = _load_verdicts() + new_verdicts
        try:
            VERDICTS_FILE.parent.mkdir(parents=True, exist_ok=True)
            VERDICTS_FILE.write_text(json.dumps(verdicts, indent=2), encoding="utf-8")
        except OSError as exc:
            _log.warning("recheck verdicts write failed: %s", exc)
    _log.info("research queue re-check: %d validated, %d discarded", len(validated), len(discarded))
    return {"validated": validated, "discarded": discarded}
