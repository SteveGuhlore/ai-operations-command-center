#!/usr/bin/env python3
"""Prospector self-learning loop.

Learns from the Prospector's OWN track record and writes a bounded calibration
back into agents/opportunity_worker.md:
  - MISTAKES: the over-penalization pattern (most deep-dives end below the
    promotion bar / rejected — usually the reflexive "saturated" downgrade), and
    score-vs-demo divergence (scored high, demoed poorly).
  - SUCCESSES: ideas whose pod booked REAL revenue (revenue ledger).

The prompt edit is confined to the delimited <!-- AUTO-CALIBRATION --> block, so
a run can never rewrite the whole persona (the old full-file Gemini rewrite was
removed — it could nuke the prompt). Invoked by the daily learning hook.
"""
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
LEDGER_FILE = ROOT / "vault" / "opportunities" / "ledger.md"
LEARNINGS_DIR = ROOT / "vault" / "learnings"
PROMPT_FILE = ROOT / "agents" / "opportunity_worker.md"

PROMOTION_BAR = 75.0
_CAL_RE = re.compile(
    r"(<!-- AUTO-CALIBRATION:START -->)(.*?)(<!-- AUTO-CALIBRATION:END -->)", re.DOTALL
)


def _rows() -> list[dict]:
    if not LEDGER_FILE.exists():
        return []
    out = []
    for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| slug") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 9:
            out.append({"slug": cells[0], "composite": cells[1], "phase": cells[2],
                        "poc": cells[3], "status": cells[6], "pod": cells[7]})
    return out


def _as_float(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def find_divergence(threshold: float = PROMOTION_BAR) -> list[dict]:
    """Scored high but demoed poorly — over-scored ideas."""
    diverging = []
    for r in _rows():
        try:
            score = float(r["composite"])
        except ValueError:
            continue
        if score >= threshold and r["poc"] in ("weak", "dead"):
            diverging.append(r)
    return diverging


def write_learnings(diverging: list[dict]) -> Path:
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out = LEARNINGS_DIR / f"{today}-opportunities.md"
    lines = [f"# Opportunity Learnings — {today}", ""]
    if diverging:
        lines.append("## Score-vs-demo divergence (scored high, demoed poorly)")
        for r in diverging:
            lines.append(f"- [[{r['slug']}]] — composite {r['composite']} but PoC {r['poc']}")
        lines.append("")
        lines.append("These patterns are over-scored. The scout should weight them down next run.")
    else:
        lines.append("_No divergence today — scoring and demos aligned._")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def find_over_penalization(rows: list[dict], min_deepdived: int = 3, reject_frac: float = 0.6) -> dict:
    """MISTAKE signal: of the deep-dived ideas, how many ended rejected or below the
    promotion bar. A high fraction means the scout is reflexively downgrading
    (the 'big but saturated' habit) so nothing ever graduates."""
    deep = [r for r in rows if r.get("phase") == "deepdived"]
    low = sum(1 for r in deep if r.get("status") == "rejected" or _as_float(r["composite"]) < PROMOTION_BAR)
    rate = (low / len(deep)) if deep else 0.0
    return {
        "triggered": len(deep) >= min_deepdived and rate >= reject_frac,
        "deepdived": len(deep),
        "low": low,
        "rate": round(rate, 3),
    }


def find_revenue_winners(rows: list[dict]) -> list[dict]:
    """SUCCESS signal: ideas whose pod booked real, logged revenue."""
    from runner.ledger.revenue import get_pod_revenue
    winners = []
    for r in rows:
        pod = (r.get("pod") or "").strip()
        if pod and pod not in ("—", "-"):
            rev = get_pod_revenue(pod)
            if rev > 0:
                winners.append({"slug": r["slug"], "revenue": round(rev, 2)})
    return winners


def build_calibration(over_pen: dict, winners: list[dict], deaths: int = 0) -> str:
    """Compose the directive text for the AUTO-CALIBRATION block. Deterministic —
    no model call, so it is safe to run often and is fully testable."""
    parts = []
    if deaths and deaths > 0:
        parts.append(
            f"**You have died {deaths} time(s).** Each death means the runway hit zero with no "
            f"real revenue and the operator had to revive you — survival is NOT guaranteed. "
            f"Remember why you died: ideas you dismissed as 'saturated' never became cash. "
            f"Do not repeat the pattern that killed you."
        )
    if over_pen.get("triggered"):
        parts.append(
            f"**Stop over-penalizing large/established markets.** Of your last "
            f"{over_pen['deepdived']} deep-dives, {over_pen['low']} ended rejected or below the "
            f"{int(PROMOTION_BAR)} promotion bar ({int(over_pen['rate'] * 100)}%) — that is the "
            f"reflexive 'saturated' downgrade keeping this pod from ever shipping a winner. A big "
            f"market is proven demand. For each idea, NAME the specific defensible wedge; only dock "
            f"points if you can show that wedge fails. Banned: rejecting an idea as merely "
            f"'saturated / competitive / crowded' without that analysis."
        )
    if winners:
        wl = ", ".join(f"[[{w['slug']}]] (${w['revenue']})" for w in winners)
        parts.append(
            f"**Reinforce what booked REAL money:** {wl}. Favor ideas resembling these in buyer, "
            f"monetization model, and wedge — real revenue beats any composite score."
        )
    if not parts:
        return "_No calibration learned yet._"
    return "\n\n".join(parts)


def update_calibration_block(text: str) -> bool:
    """Replace ONLY the content between the AUTO-CALIBRATION markers. Returns False
    if the file or markers are missing (never rewrites the whole prompt)."""
    if not PROMPT_FILE.exists():
        return False
    cur = PROMPT_FILE.read_text(encoding="utf-8")
    if not _CAL_RE.search(cur):
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    note = (f"<!-- Auto-maintained by scripts/opportunity_synthesis.py from the Prospector's own "
            f"track record — do not edit by hand. Updated {today}. -->")

    def _repl(m: "re.Match") -> str:
        return f"{m.group(1)}\n{note}\n{text}\n{m.group(3)}"

    PROMPT_FILE.write_text(_CAL_RE.sub(_repl, cur), encoding="utf-8")
    return True


def run() -> None:
    diverging = find_divergence(PROMOTION_BAR)
    write_learnings(diverging)
    rows = _rows()
    over_pen = find_over_penalization(rows)
    winners = find_revenue_winners(rows)
    deaths = 0
    try:
        from runner.ledger.runway import compute_runway
        deaths = compute_runway().get("revived_count", 0)
    except Exception:
        pass
    updated = update_calibration_block(build_calibration(over_pen, winners, deaths))
    log.info("Synthesis: divergence=%d over_penalization=%s winners=%d deaths=%d calibration_updated=%s",
             len(diverging), over_pen["triggered"], len(winners), deaths, updated)


if __name__ == "__main__":
    run()
