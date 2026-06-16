"""Pre-open reset — callable from BOTH the 09:25 cron (scripts/preopen_reset.py) and the runner
backstop (runner.main), so the routine survives even if the external scheduler is lost (as it was
in the Windows->Linux move). Cancels unfilled entries, clears the executed-log + verdicts for a
clean slate, re-checks the research queue against fresh prices, and queues the pre-open deep-dive.
Marks the day done so the cron and the backstop never double-run.
"""

import logging

from runner.ledger.market_clock import trading_day

_log = logging.getLogger(__name__)


def run_preopen_reset() -> dict:
    """Run the full pre-open routine and mark the day done. Each step is fail-soft so a single
    failure never aborts the rest. Returns a summary dict."""
    from runner.ledger import alpaca_paper as ap

    summary: dict = {}
    # Persist the day's verdicts to the learning archive BEFORE the flush empties the live file.
    # CRITICAL: only flush if archiving was CONFIRMED — otherwise we'd delete verdicts that were
    # never saved (silent daily memory loss, the thing we keep getting burned by). If it isn't
    # confirmed, keep the live file (verdicts pile up but are never lost; the health monitor alerts
    # on the multi-date backlog) and surface it to the operator.
    archived_ok = False
    try:
        from runner.ledger.tony_scorecard import archive_verdicts

        res = archive_verdicts()
        summary["archived"] = res
        archived_ok = bool(res.get("ok", False))
    except Exception as exc:
        _log.warning("verdict archive skipped: %s", exc)
        summary["archived"] = {"ok": False, "error": str(exc)}
    if archived_ok:
        summary["flush"] = ap.flush_session()
    else:
        summary["flush"] = {"skipped": "archive_not_confirmed"}
        _log.error(
            "pre-open: flush SKIPPED — verdict archive not confirmed; verdicts kept to avoid loss"
        )
        try:
            from runner.tools.notify import notify

            notify(
                "⚠️ Pre-open: verdict archive not confirmed — I skipped the daily flush so no "
                "verdicts are lost. Check workspace/tony-verdicts-archive.json."
            )
        except Exception:
            pass

    try:
        from runner.ledger.research_queue import recheck_queue

        res = recheck_queue()
        summary["recheck"] = {
            "validated": len(res.get("validated", [])),
            "discarded": len(res.get("discarded", [])),
        }
    except Exception as exc:
        _log.warning("preopen recheck skipped: %s", exc)
        summary["recheck"] = {"error": str(exc)}

    try:
        from runner.bridge import tony_bridge

        tony_bridge.make_preopen_deepdive(
            trading_day()
        )  # ET day, so cron & backstop key the same task id
        summary["deepdive"] = "queued"
    except Exception as exc:
        _log.warning("preopen deepdive skipped: %s", exc)
        summary["deepdive"] = f"error: {exc}"

    from runner.scheduler.daily_jobs import mark_preopen_ran

    mark_preopen_ran()
    return summary
