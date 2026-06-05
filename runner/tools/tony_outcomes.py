"""tony_outcomes — Tony's own track record, so he conditions on what actually works.

Read-only. Joins the bot's resolved outcomes (`tony_stocks_outcomes.json`) to Tony's
own verdicts (`tony_stocks_verdicts.json`) and summarizes:
  - the scanner BASE RATE across every resolved pick (his signal even before his own
    verdicts have closed), broken out by exit type;
  - HIS graded calls: win-rate + expectancy + avg R-multiple by verdict type, win-rate
    by confidence bucket (calibration), and per-evidence-tag edges (best/worst setups).

It reuses the pure join + grading helpers in `tony_scorecard` (no duplicated range-join)
but resolves the data files at CALL TIME from env, so tests stay isolated from the real
vault/bot files (the d5e0583 lesson). Degrades to status="awaiting_outcomes" cleanly.
"""
import os
from pathlib import Path

from runner.ledger.tony_scorecard import (
    _load, _is_right, _matched_verdict, discover_edges, sizing_attribution)

_reports = Path(__file__).parent.parent.parent.parent / "TradingBotAgentProject" / "reports"
_vault = Path(__file__).parent.parent.parent / "vault"


def _outcomes_path() -> Path:
    return Path(os.environ.get("TONY_OUTCOMES_FILE", str(_reports / "tony_stocks_outcomes.json")))


def _verdicts_path() -> Path:
    return Path(os.environ.get("TONY_VERDICTS_FILE", str(_reports / "tony_stocks_verdicts.json")))


def _pattern_library_path() -> Path:
    return Path(os.environ.get("TONY_PATTERN_LIBRARY", str(_vault / "tony-stocks" / "pattern-library.md")))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _r_multiple(o: dict, v: dict | None):
    """Realized R = (exit - entry) / (entry - stop) for a long. Needs entry/exit from the
    outcome and the stop from Tony's matched verdict. None when any leg is missing or the
    stop isn't below entry (we only model longs here)."""
    if not v:
        return None
    entry, exit_, stop = _num(o.get("entry")), _num(o.get("exit")), _num(v.get("stop"))
    if entry is None or exit_ is None or stop is None:
        return None
    risk = entry - stop
    if risk <= 0:
        return None
    return (exit_ - entry) / risk


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def get_tony_outcomes(min_edge_samples: int = 3) -> dict:
    """Summarize Tony's realized track record. Read-only; safe to call any time."""
    outcomes = _load(_outcomes_path())
    verdicts = _load(_verdicts_path())

    if not outcomes:
        return {"status": "awaiting_outcomes", "verdicts": len(verdicts),
                "note": "No resolved picks yet — the bot has not emitted outcomes."}

    # --- Scanner base rate: every resolved pick with a real return, regardless of verdict ---
    closed = [o for o in outcomes if _num(o.get("return_pct")) is not None]
    base_returns = [_num(o["return_pct"]) for o in closed]
    by_result: dict[str, int] = {}
    for o in outcomes:
        by_result[o.get("result", "unknown")] = by_result.get(o.get("result", "unknown"), 0) + 1
    scanner_base = {
        "resolved": len(outcomes),
        "with_return": len(closed),
        "pct_positive": round(sum(1 for r in base_returns if r > 0) / len(closed) * 100, 1) if closed else None,
        "avg_return_pct": _avg(base_returns),
        "avg_days_held": _avg([_num(o.get("days_held")) for o in outcomes]),
        "by_result": dict(sorted(by_result.items(), key=lambda kv: -kv[1])),
    }

    # --- Tony's graded calls: join each resolved pick to his final verdict on it ---
    by_verdict: dict[str, dict] = {}
    conf_hits: dict[str, list] = {"low": [], "medium": [], "high": []}
    edge_tally: dict[str, list] = {}
    graded = right_total = 0
    graded_returns: list = []

    for o in outcomes:
        v = _matched_verdict(o, verdicts)
        if not v:
            continue
        graded += 1
        ret = _num(o.get("return_pct")) or 0.0
        graded_returns.append(ret)
        verdict = (v.get("verdict") or "").lower()
        right = _is_right(verdict, ret)
        right_total += int(right)

        b = by_verdict.setdefault(verdict, {"n": 0, "_hits": 0, "_rets": [], "_rs": []})
        b["n"] += 1
        b["_hits"] += int(right)
        b["_rets"].append(ret)
        b["_rs"].append(_r_multiple(o, v))

        bucket = conf_hits.get(v.get("confidence", "medium"))
        if bucket is not None:
            bucket.append(int(right))
        for tag in v.get("evidence", []) or []:
            edge_tally.setdefault(tag, []).append(int(right))

    for b in by_verdict.values():
        b["win_rate"] = round(b.pop("_hits") / b["n"] * 100, 1)
        b["avg_return_pct"] = _avg(b.pop("_rets"))
        b["avg_r"] = _avg(b.pop("_rs"))

    calibration = {k: (round(sum(v) / len(v) * 100, 1) if v else None) for k, v in conf_hits.items()}

    edges = [
        {"tag": t, "n": len(rs), "win_rate": round(sum(rs) / len(rs) * 100, 1)}
        for t, rs in edge_tally.items() if len(rs) >= min_edge_samples
    ]
    edges.sort(key=lambda e: -e["win_rate"])

    tony = {
        "graded": graded,
        "win_rate": round(right_total / graded * 100, 1) if graded else None,
        "expectancy_pct": _avg(graded_returns),
        "by_verdict": by_verdict,
        "calibration": calibration,
        "best_setups": edges[:3],
        "worst_setups": edges[-3:][::-1] if len(edges) > 3 else [],
    }

    return {"status": "scored", "scanner_base": scanner_base, "tony": tony}


def _fmt_pct(x) -> str:
    return f"{x:+.1f}%" if isinstance(x, (int, float)) else "—"


def track_record_block() -> str:
    """Compact markdown for injection into Tony's brief. Always returns a short section;
    degrades to a one-liner when there are no outcomes yet."""
    rec = get_tony_outcomes()
    if rec.get("status") != "scored":
        return ("## Your Track Record\n"
                "_Awaiting resolved outcomes — no realized P&L to learn from yet. "
                "Decide on the merits; this block fills in as picks close._")

    sb = rec["scanner_base"]
    results = " · ".join(f"{n} {k}" for k, n in list(sb["by_result"].items())[:4])
    lines = [
        "## Your Track Record — condition on this, don't repeat losing setups",
        f"**Scanner base rate** ({sb['resolved']} resolved picks): "
        f"{sb['pct_positive']}% closed green · avg {_fmt_pct(sb['avg_return_pct'])} · "
        f"avg hold {sb['avg_days_held']}d · {results}",
    ]

    t = rec["tony"]
    if t["graded"]:
        verdict_bits = " · ".join(
            f"{name} {d['win_rate']}% (n={d['n']}, {d['avg_r']:+.2f}R)" if d["avg_r"] is not None
            else f"{name} {d['win_rate']}% (n={d['n']})"
            for name, d in sorted(t["by_verdict"].items(), key=lambda kv: -kv[1]["n"])
        )
        lines.append(
            f"**Your graded calls** ({t['graded']}): win-rate {t['win_rate']}% · "
            f"expectancy {_fmt_pct(t['expectancy_pct'])} per pick · {verdict_bits}"
        )
        cal = t["calibration"]
        if any(v is not None for v in cal.values()):
            cal_bits = " · ".join(f"{k} {v}%" for k, v in cal.items() if v is not None)
            lines.append(f"**Confidence calibration:** {cal_bits} — make sure 'high' actually outperforms 'low'.")
        if t["best_setups"]:
            best = " · ".join(f"{e['tag']} {e['win_rate']}% (n={e['n']})" for e in t["best_setups"])
            lines.append(f"**Best setups:** {best}")
        if t["worst_setups"]:
            worst = " · ".join(f"{e['tag']} {e['win_rate']}% (n={e['n']})" for e in t["worst_setups"])
            lines.append(f"**Fade these setups:** {worst}")
    else:
        lines.append("**Your graded calls:** none closed yet — your verdicts are still open positions.")

    sa = sizing_attribution()
    if sa.get("status") == "scored" and sa.get("graded", 0) >= 5 and sa.get("sizing_alpha_pct") is not None:
        verdict_word = "ARE earning" if sa["sizing_alpha_pct"] > 0 else "are NOT earning"
        lines.append(
            f"**Conviction sizing alpha:** {sa['sizing_alpha_pct']:+.2f}% vs flat "
            f"(conviction-weighted {sa['conviction_return_pct']:+.2f}% vs equal-weight "
            f"{sa['flat_return_pct']:+.2f}%, n={sa['graded']}) — your high-confidence calls "
            f"{verdict_word} their bigger size."
        )

    return "\n".join(lines)


def _pattern_library_excerpt(max_chars: int = 1400) -> str:
    """Pull the most recent bullet lessons Tony wrote in his weekly self-review, bounded so a
    growing library never blows the brief's token budget. Empty when the file doesn't exist yet."""
    try:
        txt = _pattern_library_path().read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return ""
    bullets = [ln.strip() for ln in txt.splitlines() if ln.strip().startswith(("-", "*"))]
    if not bullets:
        return ""
    recent, total = [], 0
    for ln in reversed(bullets):                # newest lessons are appended at the end
        if total + len(ln) > max_chars:
            break
        recent.append(ln)
        total += len(ln)
    return "\n".join(reversed(recent))


def lessons_block(min_edge_n: int = 5) -> str:
    """The learn->apply hop: surface the evidence-tag edges Tony's own graded record reveals, plus
    the bullet lessons from his pattern library, so a brief actively reminds him what wins and what
    to fade — instead of those lessons sitting unread. Empty string until there's something to say,
    so it never pads a brief before any record exists."""
    parts = []

    edges = discover_edges(min_n=min_edge_n)
    if edges.get("status") == "scored" and edges.get("edges"):
        ranked = edges["edges"]
        winners = [e for e in ranked if e["win_rate"] >= 55][:3]
        losers = [e for e in ranked if e["win_rate"] <= 45][-3:]
        if winners:
            parts.append("**Setups that win for you:** "
                         + " · ".join(f"{e['tag']} {e['win_rate']}% (n={e['n']})" for e in winners))
        if losers:
            parts.append("**Setups that lose for you — fade these:** "
                         + " · ".join(f"{e['tag']} {e['win_rate']}% (n={e['n']})" for e in losers))

    excerpt = _pattern_library_excerpt()
    if excerpt:
        parts.append("**From your pattern library:**\n" + excerpt)

    if not parts:
        return ""
    return "## Lessons From Your Own Record — apply these now\n\n" + "\n\n".join(parts) + "\n"


TOOL_SPEC = {
    "name": "tony_outcomes",
    "description": (
        "Read YOUR OWN realized track record before you decide — read-only, no side effects. "
        "Returns the scanner's base rate across all resolved picks (win %, avg return, exit-type "
        "mix), plus — once your own verdicts close — your win-rate, expectancy, and avg R-multiple "
        "by verdict type (reaffirm/adjust/override/pass/close), your win-rate by confidence bucket "
        "(is 'high' actually better than 'low'?), and your best/worst evidence-tag setups. Call it "
        "when forming a verdict so you lean into setups that have worked and fade the ones that "
        "lose. A condensed version is already shown in your brief's 'Your Track Record' section; "
        "use this tool to pull the full detail."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "min_edge_samples": {
                "type": "integer",
                "description": "Minimum resolved picks per evidence-tag before it counts as an edge (default 3).",
            },
        },
        "required": [],
    },
}
