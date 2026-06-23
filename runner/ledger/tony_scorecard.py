"""tony_scorecard — grades Tony's verdicts against the trading bot's outcomes.

Join key: (symbol, pick_date == the verdict's `date`). Grading rule:
  bullish (reaffirm/adjust) is RIGHT  if outcome return_pct > 0
  step-off (override/pass/close) is RIGHT if outcome return_pct <= 0  (correctly avoided a loser)

Produces the second track record + agreement matrix (Cockpit) and per-confidence
calibration. Degrades to status="awaiting_outcomes" when the bot hasn't emitted outcomes
yet — see docs/handoffs/2026-06-02-tony-loop-and-cockpit.md §4.
"""

import json
import logging
import math
import os
from pathlib import Path

from runner.ledger._jsonio import atomic_write_json, load_dict, load_list

_log = logging.getLogger(__name__)

_reports = (
    Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"
)
_vault = Path(__file__).parent.parent.parent / "vault"
VERDICTS_FILE = Path(
    os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json"))
)
# Learning archive: the live verdicts file is FLUSHED daily (needed for execution), which otherwise
# wipes the verdict->outcome history the scorecard learns from. archive_verdicts() appends each day's
# verdicts here before the flush, and grading reads archive UNION live so learning accumulates.
VERDICTS_ARCHIVE = Path(
    os.environ.get(
        "TONY_VERDICTS_ARCHIVE",
        str(
            Path(__file__).parent.parent.parent
            / "workspace"
            / "tony-verdicts-archive.json"
        ),
    )
)
OUTCOMES_FILE = Path(
    os.environ.get("TONY_OUTCOMES_FILE", str(_reports / "tony_stocks_outcomes.json"))
)
RECORD_FILE = Path(
    os.environ.get("TONY_RECORD_FILE", str(_reports / "tony_stocks_record.json"))
)
# Tony's weekly self-review reads the record alongside his other vault files, so mirror it there too.
VAULT_RECORD_FILE = Path(
    os.environ.get(
        "TONY_VAULT_RECORD_FILE",
        str(_vault / "tony-stocks" / "tony_stocks_record.json"),
    )
)
# Monotonic grade archive: compute_record re-grades from scratch each run, so a pick can DROP out of
# the "2nd pass" tally if a later recompute fails to re-match it (verdict rotated out of the archive,
# outcome aged past the emit window, ET/UTC date skew on the join). write_record locks each resolved
# (symbol, pick_date) grade here permanently so the published record never shrinks — the same
# terminal-lock the bot's divergence ledger uses. Keyed "SYMBOL|pick_date".
GRADED_ARCHIVE = Path(
    os.environ.get(
        "TONY_GRADED_ARCHIVE",
        str(
            Path(__file__).parent.parent.parent
            / "workspace"
            / "tony-graded-archive.json"
        ),
    )
)

_BULLISH = {"reaffirm", "adjust"}


def _verdict_key(v) -> tuple:
    return (str(v.get("date", "")), str(v.get("symbol", "")).upper())


def _archive_sibling(ext: str) -> Path:
    return VERDICTS_ARCHIVE.with_suffix(VERDICTS_ARCHIVE.suffix + ext)


def _read_archive_list() -> tuple[list, bool]:
    """(verdicts, ok). ok=False means the archive file EXISTS but failed to parse (corrupt) — the
    caller must NOT treat that as 'empty', or the next write would wipe the accumulated history."""
    try:
        data = json.loads(VERDICTS_ARCHIVE.read_text(encoding="utf-8"))
        return (data if isinstance(data, list) else [], True)
    except FileNotFoundError:
        return ([], True)  # genuinely no archive yet — safe to build fresh
    except (json.JSONDecodeError, OSError) as exc:
        _log.error("verdict archive unreadable (%s) — recovering from backup", exc)
        return ([], False)


def _atomic_write_archive(merged: list) -> bool:
    """Write the archive atomically (tmp + os.replace, no truncation window) and keep a rolling
    .bak as last-known-good for corruption recovery. Returns True on success."""
    try:
        VERDICTS_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _archive_sibling(".tmp")
        tmp.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        os.replace(tmp, VERDICTS_ARCHIVE)
        try:
            _archive_sibling(".bak").write_text(
                json.dumps(merged, indent=2), encoding="utf-8"
            )
        except OSError:
            pass  # backup is best-effort; the primary write already succeeded
        return True
    except OSError as exc:
        _log.error("verdict archive write failed: %s", exc)
        return False


def archive_verdicts() -> dict:
    """Append the current (about-to-be-flushed) verdicts to the persistent learning archive so the
    scorecard can grade verdict->outcome over time. Called from the pre-open reset BEFORE the flush
    empties the live file. Dedup by (date, symbol), latest wins.

    Hardened so the daily flush can never silently lose Tony's memory: atomic write + rolling
    backup; on a corrupt archive, recover from the backup (and quarantine the bad file) instead of
    rebuilding from today's live file only; and a monotonic guard that refuses to shrink. Returns an
    ``ok`` flag — run_preopen_reset gates the flush on it, so verdicts are never deleted unsaved."""
    live = _load(VERDICTS_FILE)
    arch, ok = _read_archive_list()
    if not ok:
        try:
            bak = json.loads(_archive_sibling(".bak").read_text(encoding="utf-8"))
            arch = bak if isinstance(bak, list) else []
            _log.warning(
                "verdict archive recovered %d verdict(s) from backup", len(arch)
            )
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            arch = []
        try:  # quarantine the corrupt file for inspection rather than overwrite it blindly
            VERDICTS_ARCHIVE.replace(_archive_sibling(".corrupt"))
        except OSError:
            pass
    by_key = {_verdict_key(v): v for v in arch if v.get("symbol") and v.get("date")}
    before = len(by_key)
    for v in live:
        if v.get("symbol") and v.get("date"):
            by_key[_verdict_key(v)] = v
    merged = sorted(
        by_key.values(),
        key=lambda v: (str(v.get("date", "")), str(v.get("symbol", ""))),
    )
    # Monotonic guard: a healthy read must never shrink (a union can't, but a bug/bad input could).
    if ok and len(merged) < before:
        _log.error(
            "verdict archive would shrink %d->%d — refusing to overwrite",
            before,
            len(merged),
        )
        return {"archived": 0, "total": before, "ok": False}
    written = _atomic_write_archive(merged)
    return {"archived": len(merged) - before, "total": len(merged), "ok": written}


def _all_verdicts() -> list:
    """Full verdict history for grading: the persistent archive UNION today's live verdicts (deduped
    by date+symbol, latest wins). The live file is flushed daily, so the archive is what lets the
    scorecard/edge-mining/calibration learn off the FULL record instead of a single starved day."""
    by_key: dict = {}
    for v in _load(VERDICTS_ARCHIVE) + _load(VERDICTS_FILE):
        if v.get("symbol") and v.get("date"):
            by_key[_verdict_key(v)] = v
    return list(by_key.values())


def _load(p) -> list:
    return load_list(p)


def _is_right(verdict: str, ret: float, source: str = "") -> bool:
    # A research_queue_recheck 'override' is an AUTO long entry (a queue survivor the system
    # bought), not a step-off — so it's right when it goes UP, like the other bullish entries.
    bullish = verdict in _BULLISH or source == "research_queue_recheck"
    return ret > 0 if bullish else ret <= 0


def _episode_upper_bounds(outcomes: list) -> dict:
    """For each resolved pick, the EXCLUSIVE upper bound for attributing verdicts to it = the
    symbol's NEXT pick_date (or None for its latest episode). A verdict belongs to the episode
    whose window [pick_date, next_pick_date) it falls in, so a verdict reviewing a re-pick is
    never stolen by the symbol's earlier, already-resolved episode. Keyed (SYMBOL, pick_date)."""
    from collections import defaultdict  # noqa: PLC0415

    by_sym: dict[str, set] = defaultdict(set)
    for o in outcomes or []:
        sym = str(o.get("symbol") or "").upper()
        pd = str(o.get("pick_date") or "")
        if sym and pd:
            by_sym[sym].add(pd)
    bounds: dict[tuple[str, str], str | None] = {}
    for sym, pds in by_sym.items():
        ordered = sorted(pds)
        for i, pd in enumerate(ordered):
            bounds[(sym, pd)] = ordered[i + 1] if i + 1 < len(ordered) else None
    return bounds


def _matched_verdict(
    o: dict, verdicts: list, next_pick_date: str | None = None
) -> dict | None:
    """Match a resolved pick to Tony's verdict. Prefer a shared pick_id; otherwise join on
    symbol + verdict date >= pick_date, taking his LATEST (final) call. This survives
    entry_date != bridge_date and the fact that Tony only verdicts on Tier-1 days.

    NB there is intentionally NO ``verdict_date <= resolved_date`` upper bound: a pick that
    resolved fast (a same-day stop-out, or a Tier-3 name Tony only reaches on a later fan-out)
    is still graded against the call he made on it, instead of silently dropping out of the
    "2nd pass" tally. ``next_pick_date`` (the symbol's next episode, exclusive) bounds the
    window so a verdict reviewing a re-pick is attributed to that re-pick, not this episode."""
    pid = o.get("pick_id")
    if pid:
        cands = [v for v in verdicts if v.get("pick_id") == pid]
    else:
        sym = str(o.get("symbol") or "").upper()
        pd = o.get("pick_date")
        cands = [
            v
            for v in verdicts
            if str(v.get("symbol") or "").upper() == sym
            and v.get("date")
            and (not pd or v["date"] >= pd)
            and (next_pick_date is None or v["date"] < next_pick_date)
        ]
    return max(cands, key=lambda v: v.get("date", "")) if cands else None


# Agreement-block keys are the EXACT contract the bot's CommandCenterAgreement schema reads
# (schemas.py). Do not rename without coordinating: agreed_right, agreed_wrong,
# cc_overrode_saved, cc_overrode_missed.
def _empty_agreement() -> dict:
    return {
        "agreed_right": 0,
        "agreed_wrong": 0,
        "cc_overrode_saved": 0,
        "cc_overrode_missed": 0,
    }


def _awaiting_record(verdict_count: int) -> dict:
    return {
        "status": "awaiting_outcomes",
        "verdicts": verdict_count,
        "graded": 0,
        "win_rate": 0.0,
        "tony_win_rate": 0.0,
        "avg_pl_per_trade": None,
        "target_hits": 0,
        "stop_hits": 0,
        "agreement": _empty_agreement(),
        "calibration": {"low": None, "medium": None, "high": None},
    }


def _grade_key(pick: dict) -> str:
    return f"{pick['symbol']}|{pick['pick_date']}"


def _iter_graded(verdicts: list, outcomes: list) -> list[dict]:
    """One graded record per RESOLVED pick Tony verdicted, using the episode-bounded relaxed
    join. Each carries everything _aggregate (and the monotonic archive) needs to re-tally
    without re-reading the source files: symbol, pick_date, quadrant, right, return_pct,
    result, confidence."""
    bounds = _episode_upper_bounds(outcomes)
    picks: list[dict] = []
    for o in (
        outcomes or []
    ):  # one grade per RESOLVED pick (his final call before it closed)
        sym = str(o.get("symbol") or "").upper()
        pick_date = str(o.get("pick_date") or "")
        v = _matched_verdict(o, verdicts, next_pick_date=bounds.get((sym, pick_date)))
        if not v:
            continue
        ret = float(o.get("return_pct", 0) or 0)
        verdict = v.get("verdict", "")
        if verdict in _BULLISH:
            quadrant = "agreed_right" if ret > 0 else "agreed_wrong"
        else:
            quadrant = "cc_overrode_saved" if ret <= 0 else "cc_overrode_missed"
        picks.append(
            {
                "symbol": sym,
                "pick_date": pick_date,
                "quadrant": quadrant,
                "right": _is_right(verdict, ret, v.get("source", "")),
                "return_pct": o.get("return_pct"),
                "result": o.get("result"),
                "confidence": v.get("confidence", "medium"),
            }
        )
    return picks


def _aggregate(picks: list[dict], verdict_count: int) -> dict:
    """Build the scored record dict from a list of graded picks (fresh or archive-merged)."""
    graded = tony_right = target_hits = stop_hits = 0
    pl_values: list = []
    agg = _empty_agreement()
    conf_buckets: dict[str, list] = {"low": [], "medium": [], "high": []}

    for p in picks:
        graded += 1
        if p.get("return_pct") is not None:
            pl_values.append(float(p["return_pct"]))
        if p.get("result") == "target_hit":
            target_hits += 1
        elif p.get("result") == "stop_hit":
            stop_hits += 1
        right = bool(p.get("right"))
        tony_right += int(right)
        agg[p["quadrant"]] += 1
        bucket = conf_buckets.get(p.get("confidence", "medium"))
        if bucket is not None:
            bucket.append(int(right))

    calibration = {
        k: round(sum(b) / len(b) * 100, 1) if b else None
        for k, b in conf_buckets.items()
    }
    win_rate = round(tony_right / graded * 100, 1) if graded else 0.0
    avg_pl = round(sum(pl_values) / len(pl_values), 2) if pl_values else None

    return {
        "status": "scored",
        "verdicts": verdict_count,
        "graded": graded,
        "win_rate": win_rate,
        "tony_win_rate": win_rate,  # back-compat alias (tony_live_guard reads this)
        "avg_pl_per_trade": avg_pl,
        "target_hits": target_hits,
        "stop_hits": stop_hits,
        "agreement": agg,
        "calibration": calibration,
    }


def compute_record() -> dict:
    """Fresh scorecard from the current verdicts (archive ∪ live) and outcomes. Non-monotonic
    by design — callers that need the live win-rate (tony_live_guard, daily audit) read this.
    The PUBLISHED record (write_record) overlays the monotonic grade archive on top."""
    verdicts = _all_verdicts()
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return _awaiting_record(len(verdicts))
    return _aggregate(_iter_graded(verdicts, outcomes), len(verdicts))


def _load_graded_archive() -> dict:
    return load_dict(GRADED_ARCHIVE)


def _merge_graded_archive(fresh: list[dict]) -> list[dict]:
    """Lock each resolved (symbol, pick_date) grade permanently and return the merged set.
    The FIRST terminal grade for a pick wins and is never overwritten/flipped, so the 2nd-pass
    tally only grows — even when a later recompute can't re-match the pick. Outcomes only ever
    carry resolved picks, so every graded record here is terminal (no pending to accumulate)."""
    archive = _load_graded_archive()
    changed = False
    for p in fresh:
        key = _grade_key(p)
        if key not in archive:
            archive[key] = p
            changed = True
    if changed:
        try:
            atomic_write_json(GRADED_ARCHIVE, archive, indent=2)
        except OSError as exc:
            _log.warning("graded archive write failed: %s", exc)
    return list(archive.values())


def discover_edges(min_n: int = 5) -> dict:
    """Mine graded picks for evidence-tag → win-rate edges (>= min_n samples each)."""
    verdicts = _all_verdicts()
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return {"status": "insufficient_history", "edges": []}
    tally: dict[str, list] = {}
    for o in outcomes:
        v = _matched_verdict(o, verdicts)
        if not v:
            continue
        right = int(
            _is_right(
                v.get("verdict", ""),
                float(o.get("return_pct", 0) or 0),
                v.get("source", ""),
            )
        )
        for tag in v.get("evidence", []) or []:
            tally.setdefault(tag, []).append(right)
    edges = [
        {"tag": tag, "n": len(rs), "win_rate": round(sum(rs) / len(rs) * 100, 1)}
        for tag, rs in tally.items()
        if len(rs) >= min_n
    ]
    edges.sort(key=lambda e: -e["win_rate"])
    return {"status": "scored" if edges else "insufficient_history", "edges": edges}


_OPEN_VERDICTS = {
    "reaffirm",
    "adjust",
    "override",
}  # the verdicts that become sized positions


def sizing_attribution() -> dict:
    """B1 honest-measurement: decompose Tony's realized return into picking vs sizing alpha,
    WITHOUT a second account. Realized return_pct is sizing-independent, so weighting each pick by
    its conviction multiplier and comparing to the equal-weight mean isolates what conviction
    sizing alone contributes. Lets B1 run in shadow (real sizing flat) and still be measured."""
    verdicts = _all_verdicts()
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        return {
            "status": "awaiting_outcomes",
            "graded": 0,
            "picking_alpha_pct": None,
            "flat_return_pct": None,
            "conviction_return_pct": None,
            "sizing_alpha_pct": None,
        }
    try:
        from runner.ledger.alpaca_paper import conviction_multiplier
    except Exception:

        def conviction_multiplier(
            _c,
        ):  # degrade to flat weighting if sizing module unavailable
            return 1.0

    rets, w_sum, w_ret, graded = [], 0.0, 0.0, 0
    for o in outcomes:
        v = _matched_verdict(o, verdicts)
        if not v or (v.get("verdict") or "").lower() not in _OPEN_VERDICTS:
            continue  # only entries get a conviction-scaled size
        ret = float(o.get("return_pct", 0) or 0)
        w = conviction_multiplier(v.get("confidence"))
        rets.append(ret)
        w_sum += w
        w_ret += w * ret
        graded += 1
    if not rets:
        return {
            "status": "awaiting_outcomes",
            "graded": 0,
            "picking_alpha_pct": None,
            "flat_return_pct": None,
            "conviction_return_pct": None,
            "sizing_alpha_pct": None,
        }
    flat = sum(rets) / len(rets)
    conv = w_ret / w_sum if w_sum else flat
    # picking_alpha = selection quality at equal (flat) sizing; sizing_alpha = the extra from
    # conviction weighting. The execution-parity v1.1 §B.1 contract names these two explicitly.
    return {
        "status": "scored",
        "graded": graded,
        "picking_alpha_pct": round(flat, 3),
        "flat_return_pct": round(flat, 3),  # alias kept for the brief's wording
        "conviction_return_pct": round(conv, 3),
        "sizing_alpha_pct": round(conv - flat, 3),
    }


def _tony_equity_curve() -> list:
    """Tony's normalized equity series (indexed to 100, live-marked) for the head-to-head, pulled
    from equity_history. Best-effort: returns [] if the history isn't available yet."""
    try:
        from runner.ledger import equity_history

        pts = equity_history.curve().get("points", [])
        return [p["tony"] for p in pts if p.get("tony") is not None]
    except Exception as exc:
        _log.info("equity_curve for record unavailable: %s", exc)
        return []


def _sanitize(obj):
    """NaN/inf -> None: the bot's record reader requires strict-JSON-safe numbers."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def write_record() -> dict:
    # Publish the MONOTONIC record: grade fresh, then merge into the locked grade archive so the
    # "2nd pass" tally only ever grows (a recompute that loses a match can't shrink the panel).
    verdicts = _all_verdicts()
    outcomes = _load(OUTCOMES_FILE)
    if not outcomes:
        rec = _awaiting_record(len(verdicts))
    else:
        merged = _merge_graded_archive(_iter_graded(verdicts, outcomes))
        rec = _aggregate(merged, len(verdicts))
    rec["equity_curve"] = (
        _tony_equity_curve()
    )  # list[float], indexed to 100, live-marked
    rec["sizing_attribution"] = (
        sizing_attribution()
    )  # B1: picking vs sizing alpha (optional field)
    rec = _sanitize(rec)
    payload = json.dumps(rec, indent=2, allow_nan=False)
    for target in (RECORD_FILE, VAULT_RECORD_FILE):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
        except OSError as exc:
            _log.warning("write_record failed for %s: %s", target, exc)
    return rec
