#!/usr/bin/env python3
"""Clay (builder) design self-learning loop.

Reads Clay's running design log (vault/builder/design_log.md) and what actually
converted (revenue ledger), then writes learned design rules into the bounded
<!-- DESIGN-CALIBRATION --> block of agents/builder.md so he gets better at
web design over time — for both graduated product landings and Pitch's Easy
Simple Sites client work. Same pattern as opportunity_synthesis. Invoked by the
daily learning hook.
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
DESIGN_LOG = ROOT / "vault" / "builder" / "design_log.md"
PROMPT_FILE = ROOT / "agents" / "builder.md"
HOUSE_STYLE_SKILL = ROOT / "vault" / "builder" / "skills" / "clay-house-style" / "SKILL.md"

_CAL_RE = re.compile(
    r"(<!-- DESIGN-CALIBRATION:START -->)(.*?)(<!-- DESIGN-CALIBRATION:END -->)", re.DOTALL
)


def parse_log() -> list[dict]:
    """Parse the design log table into rows: {date, slug, type, archetype, ...}."""
    if not DESIGN_LOG.exists():
        return []
    rows = []
    for line in DESIGN_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or "archetype" in line.lower() or set(line) <= set("|- "):
            continue
        c = [x.strip() for x in line.strip("|").split("|")]
        if len(c) >= 4:
            rows.append({"date": c[0], "slug": c[1], "type": c[2], "archetype": c[3],
                         "palette": c[4] if len(c) > 4 else "",
                         "fonts": c[5] if len(c) > 5 else "",
                         "notes": c[6] if len(c) > 6 else ""})
    return rows


def find_overused_archetype(rows: list[dict], recent: int = 8, threshold: float = 0.5) -> dict:
    """If one archetype dominates the last `recent` builds, flag it for rotation
    (the 'every site looks the same' failure)."""
    window = [r["archetype"] for r in rows[-recent:] if r.get("archetype")]
    if len(window) < 3:
        return {"triggered": False, "archetype": None, "count": 0, "window": len(window)}
    counts: dict[str, int] = {}
    for a in window:
        counts[a] = counts.get(a, 0) + 1
    top, top_n = max(counts.items(), key=lambda kv: kv[1])
    return {
        "triggered": top_n / len(window) >= threshold,
        "archetype": top,
        "count": top_n,
        "window": len(window),
    }


def find_winning_archetypes(rows: list[dict]) -> list[dict]:
    """Archetypes used on sites whose pod booked REAL revenue — reinforce these."""
    from runner.ledger.revenue import get_pod_revenue
    winners = []
    seen = set()
    for r in rows:
        slug = (r.get("slug") or "").strip()
        arch = (r.get("archetype") or "").strip()
        if not slug or not arch or slug in seen:
            continue
        rev = get_pod_revenue(slug)
        if rev > 0:
            winners.append({"slug": slug, "archetype": arch, "revenue": round(rev, 2)})
            seen.add(slug)
    return winners


def build_design_calibration(overused: dict, winners: list[dict]) -> str:
    parts = []
    if overused.get("triggered"):
        parts.append(
            f"**Rotate your archetypes.** You used **{overused['archetype']}** for "
            f"{overused['count']} of your last {overused['window']} builds — sites are starting to "
            f"look the same (AI slop). Deliberately pick a DIFFERENT archetype next, and vary the "
            f"layout/structure, not just colors and words."
        )
    if winners:
        wl = ", ".join(f"[[{w['slug']}]] → {w['archetype']} (${w['revenue']})" for w in winners)
        parts.append(
            f"**Repeat what converted:** these sites booked real money — {wl}. Lean toward the "
            f"design language that earned, for similar buyers."
        )
    if not parts:
        return "_No design calibration learned yet._"
    return "\n\n".join(parts)


def update_calibration_block(text: str) -> bool:
    if not PROMPT_FILE.exists():
        return False
    cur = PROMPT_FILE.read_text(encoding="utf-8")
    if not _CAL_RE.search(cur):
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    note = (f"<!-- Auto-maintained by scripts/design_synthesis.py from the builder's own design log "
            f"+ outcomes — do not edit by hand. Updated {today}. -->")

    def _repl(m: "re.Match") -> str:
        return f"{m.group(1)}\n{note}\n{text}\n{m.group(3)}"

    PROMPT_FILE.write_text(_CAL_RE.sub(_repl, cur), encoding="utf-8")
    return True


def author_house_style_skill(rows: list[dict], overused: dict, winners: list[dict]) -> bool:
    """Author Clay's OWN skill from his track record. Pages that booked real revenue define
    his house style; this writes a first-class SKILL.md that the loader injects as a CORE
    skill — so over time the library's many skills merge into one that is genuinely his."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---",
        "name: clay-house-style",
        "description: Clay's own design style, learned from landing pages that booked real "
        "revenue. Auto-generated by design_synthesis.py — do not edit by hand.",
        "---",
        "",
        f"# Clay House Style (learned {today})",
        "",
        "Your own evolving design skill, distilled from real build outcomes. Apply it first, "
        "then reach into the wider design library for specifics.",
        "",
    ]
    if winners:
        by_slug: dict[str, dict] = {}
        for r in rows:
            by_slug.setdefault((r.get("slug") or "").strip(), r)
        lines.append("## What has actually converted (real revenue)")
        for w in winners:
            r = by_slug.get(w["slug"], {})
            extra = ", ".join(x for x in (r.get("palette", ""), r.get("fonts", "")) if x)
            extra = f" — {extra}" if extra else ""
            lines.append(f"- **{w['archetype']}** on [[{w['slug']}]] (${w['revenue']}){extra}")
        lines.append("")
        lines.append("Lean toward these design languages for similar buyers — they earned money.")
        lines.append("")
    else:
        lines.append("_Still forming — no revenue-confirmed builds yet. Rotate archetypes, vary "
                     "layout/structure (not just colors), and avoid AI-slop sameness._")
        lines.append("")
    if overused.get("triggered"):
        lines.append(
            f"## Currently overused\nYou have leaned on **{overused['archetype']}** too often "
            f"({overused['count']}/{overused['window']} recent builds) — pick something different next.\n"
        )
    lines += [
        "## Standing principles",
        "- Rotate archetypes; never ship two look-alike pages in a row.",
        "- Vary layout and structure, not just palette and copy.",
        "- One clear CTA; make the value obvious above the fold.",
        "- Real craft over decoration — enough polish to earn trust and a payment.",
        "",
    ]
    HOUSE_STYLE_SKILL.parent.mkdir(parents=True, exist_ok=True)
    HOUSE_STYLE_SKILL.write_text("\n".join(lines), encoding="utf-8")
    return True


def run() -> None:
    rows = parse_log()
    overused = find_overused_archetype(rows)
    winners = find_winning_archetypes(rows)
    updated = update_calibration_block(build_design_calibration(overused, winners))
    authored = author_house_style_skill(rows, overused, winners)
    log.info("Design synthesis: builds=%d overused=%s winners=%d calibration_updated=%s house_style=%s",
             len(rows), overused.get("triggered"), len(winners), updated, authored)


if __name__ == "__main__":
    run()
