"""Tony-dashboard routes — registered on the main FastAPI app via include_router.

All routes are null-safe: sub-failures degrade to empty/None rather than 500.
RESEARCH / PAPER only — no order, risk, or sizing logic here.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

# _load_verdicts is re-used from the main server module to share the guarded loader.
# Import lazily inside each handler so startup is not blocked by missing deps.


def _load_verdicts_local(path) -> list:
    import json

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


@router.get("/tony", response_class=HTMLResponse)
async def tony_dashboard():
    html_file = Path(__file__).parent / "tony.html"
    try:
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    except OSError:
        return HTMLResponse(
            content="<h1>Tony dashboard unavailable</h1>", status_code=503
        )


@router.get("/api/tony/record")
async def api_tony_record():
    try:
        from runner.ledger.tony_scorecard import compute_record

        return compute_record()
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@router.get("/api/tony/agreement")
async def api_tony_agreement():
    try:
        from runner.ledger.tony_scorecard import compute_record

        rec = compute_record()
        return {
            "status": rec.get("status"),
            "graded": rec.get("graded"),
            "agreement": rec.get("agreement"),
            "calibration": rec.get("calibration"),
        }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/api/spx")
async def api_spx():
    try:
        from runner.ledger import alpaca_paper as ap

        return ap.spy_closes(15)
    except Exception as exc:
        return {"closes": [], "src": "none", "error": str(exc)}


@router.get("/api/marks")
async def api_marks(syms: str = ""):
    from runner.ledger import alpaca_paper as ap

    arr = [s for s in (syms or "").split(",") if s.strip()]
    if not arr:
        return {"trades": {}}
    try:
        return ap.latest_trade_prices(arr)
    except Exception as exc:
        return {"trades": {}, "src": "none", "error": str(exc)}


@router.get("/api/tony/live")
async def api_tony_live():
    """Aggregator endpoint: all data the standalone Tony dashboard needs in one call.

    Degrades section-by-section — any sub-failure sets sim=True and returns empty/None
    for that section rather than raising a 500.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    asof = datetime.now(ZoneInfo("America/New_York")).isoformat()
    sim = False

    # --- scorecard ---
    try:
        from runner.ledger.tony_scorecard import compute_record

        rec = compute_record()
    except Exception:
        rec = {}
        sim = True

    rec_status = rec.get("status", "")
    if rec_status not in ("scored", "ok"):
        sim = True

    agreement = rec.get("agreement") or {}
    calibration = rec.get("calibration") or {}
    stats = {
        "call_accuracy_pct": (
            rec.get("tony_win_rate")
            if rec.get("tony_win_rate") is not None
            else rec.get("win_rate")
        ),
        "avg_pl_per_trade": rec.get("avg_pl_per_trade"),
        "graded": rec.get("graded") or 0,
        "open_positions": 0,
    }
    quadrant = {
        "agreed_right": agreement.get("agreed_right") or 0,
        "agreed_wrong": agreement.get("agreed_wrong") or 0,
        "tony_saved": agreement.get("cc_overrode_saved") or 0,
        "tony_missed": agreement.get("cc_overrode_missed") or 0,
    }

    # --- paper book ---
    book_rows = []
    live_prices: dict = {}
    try:
        from runner.ledger import alpaca_paper as ap
        from runner.ledger.equity_history import mark_live

        book = ap.paper_book()
        if book.get("status") == "ok":
            mark_live(book)
        else:
            sim = True
        positions = book.get("open_positions") or []
        stats["open_positions"] = len(positions)
        for p in positions:
            sym = p.get("symbol") or ""
            upl = p.get("unrealized_pl")
            if upl is not None:
                upl_f = float(upl)
                sign = "+" if upl_f >= 0 else "−"  # Unicode minus for negatives
                unreal_str = sign + "$" + str(round(abs(upl_f), 2))
                up = upl_f >= 0
            else:
                unreal_str = ""
                up = True
            entry = p.get("avg_entry_price")
            last = p.get("current_price")
            book_rows.append(
                {
                    "sym": sym,
                    "qty": str(p.get("qty") or ""),
                    "entry": ("$" + str(round(float(entry), 2)))
                    if entry is not None
                    else "",
                    "last": ("$" + str(round(float(last), 2)))
                    if last is not None
                    else "",
                    "unreal": unreal_str,
                    "up": up,
                }
            )
            if sym and last is not None:
                live_prices[sym.upper()] = float(last)
    except Exception:
        sim = True

    # --- equity curve ---
    equity_out: dict = {
        "labels": [],
        "tony": [],
        "bot": [],
        "tony_return_pct": None,
        "bot_return_pct": None,
    }
    try:
        from runner.ledger.equity_history import curve

        eq = curve()
        pts = eq.get("points") or []
        equity_out["tony"] = [p["tony"] for p in pts if p.get("tony") is not None]
        equity_out["bot"] = [p["bot"] for p in pts if p.get("bot") is not None]
        equity_out["labels"] = [p.get("ts") or p.get("label") or "" for p in pts]
        equity_out["tony_return_pct"] = eq.get("tony_return_pct")
        equity_out["bot_return_pct"] = eq.get("bot_return_pct")
    except Exception:
        sim = True

    # --- verdicts, calls, projections ---
    calls_out = []
    projections_out: dict = {}
    try:
        from runner.ledger import alpaca_paper as _ap

        verdicts = _load_verdicts_local(_ap.VERDICTS_FILE)
        try:
            levels = _ap._latest_scanner_levels()
        except Exception:
            levels = {}

        sorted_verdicts = sorted(
            verdicts, key=lambda v: v.get("date") or "", reverse=True
        )
        for v in sorted_verdicts[:12]:
            sym = (v.get("symbol") or "").upper()
            verdict_str = v.get("verdict") or ""
            thesis = v.get("thesis") or ""
            grade = "open"
            ret = (
                v.get("returned_pct")
                if v.get("returned_pct") is not None
                else v.get("return_pct")
            )
            if ret is not None:
                try:
                    grade = "win" if float(ret) > 0 else "loss"
                except (TypeError, ValueError):
                    grade = "open"
            calls_out.append(
                {
                    "sym": sym,
                    "verb": verdict_str.title(),
                    "note": thesis[:90].rstrip() if thesis else "",
                    "time": v.get("time") or "",
                    "day": "today",
                    "grade": grade,
                }
            )

            lvl = levels.get(sym) or {}
            last_price = live_prices.get(sym)
            if last_price is None:
                last_price = lvl.get("target") or v.get("target")
            if last_price is not None:
                try:
                    from runner.ledger.tony_horizon import projection_for_verdict

                    proj = projection_for_verdict(
                        last_price,
                        verdict_str,
                        scanner_target=lvl.get("target"),
                        scanner_stop=lvl.get("stop"),
                        tony_target=v.get("target"),
                        tony_stop=v.get("stop"),
                        confidence=v.get("confidence", "medium"),
                    )
                    if proj is not None:
                        proj["confidence"] = v.get("confidence", "medium")
                        projections_out[sym] = proj
                except Exception:
                    pass
    except Exception:
        sim = True

    return {
        "status": rec_status or "awaiting",
        "asof": asof,
        "sim": sim,
        "stats": stats,
        "quadrant": quadrant,
        "calibration": {
            "low": calibration.get("low"),
            "medium": calibration.get("medium"),
            "high": calibration.get("high"),
        },
        "equity": equity_out,
        "book": book_rows,
        "calls": calls_out,
        "projections": projections_out,
    }
