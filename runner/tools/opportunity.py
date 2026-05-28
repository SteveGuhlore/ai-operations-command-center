# runner/tools/opportunity.py
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
OPP_DIR = BASE_DIR / "vault" / "opportunities"
LEDGER_FILE = OPP_DIR / "ledger.md"

_WEIGHTS = {
    "willingness_to_pay": 0.25,
    "revenue_potential": 0.20,
    "problem_severity": 0.15,
    "buildability": 0.15,
    "system_fit": 0.15,
    "novelty": 0.10,
}

_LEDGER_HEADER = (
    "# Opportunity Ledger\n\n"
    "| slug | composite | phase | poc | system_fit | est_rev_mo | status | pod | updated |\n"
    "|------|-----------|-------|-----|-----------|-----------|--------|-----|--------|\n"
)


def composite_score(
    willingness_to_pay: float, revenue_potential: float, problem_severity: float,
    buildability: float, system_fit: float, novelty: float,
) -> float:
    dims = {
        "willingness_to_pay": willingness_to_pay,
        "revenue_potential": revenue_potential,
        "problem_severity": problem_severity,
        "buildability": buildability,
        "system_fit": system_fit,
        "novelty": novelty,
    }
    weighted = sum(_WEIGHTS[k] * float(v) for k, v in dims.items())
    return round(weighted * 10, 2)


def _ensure_ledger() -> str:
    OPP_DIR.mkdir(parents=True, exist_ok=True)
    if not LEDGER_FILE.exists():
        LEDGER_FILE.write_text(_LEDGER_HEADER, encoding="utf-8")
    return LEDGER_FILE.read_text(encoding="utf-8")


def _slug_in_ledger(ledger: str, slug: str) -> bool:
    return f"| {slug} |" in ledger


def read_ledger() -> list[dict]:
    """Parse ledger.md rows so the runner can drive the opportunity pipeline."""
    if not LEDGER_FILE.exists():
        return []
    rows = []
    for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| slug") or set(line) <= set("|- "):
            continue
        c = [x.strip() for x in line.strip("|").split("|")]
        if len(c) < 9:
            continue
        try:
            comp = float(c[1])
        except ValueError:
            comp = 0.0
        rows.append({"slug": c[0], "composite": comp, "phase": c[2], "poc": c[3],
                     "system_fit": c[4], "est_rev_mo": c[5], "status": c[6],
                     "pod": c[7], "updated": c[8]})
    return rows


def log_opportunity(
    slug: str, one_liner: str, problem: str, who_pays: str,
    willingness_to_pay: float, revenue_potential: float, problem_severity: float,
    buildability: float, system_fit: float, novelty: float,
    est_rev_mo: float = 0.0,
) -> dict:
    try:
        ledger = _ensure_ledger()
        if _slug_in_ledger(ledger, slug):
            return {"skipped": True, "reason": f"{slug} already in ledger", "slug": slug}

        composite = composite_score(
            willingness_to_pay, revenue_potential, problem_severity,
            buildability, system_fit, novelty,
        )
        today = datetime.now().strftime("%Y-%m-%d")
        row = (
            f"| {slug} | {composite} | scouted | — | {system_fit} | "
            f"{est_rev_mo or '—'} | scouted | — | {today} |\n"
        )
        LEDGER_FILE.write_text(ledger + row, encoding="utf-8")

        page = OPP_DIR / f"{slug}.md"
        page.write_text(
            f"# {slug}\n\n"
            f"> {one_liner}\n\n"
            f"Backlinks: [[ledger]] · [[_moc]]\n\n"
            f"## Scores ({today})\n"
            f"- willingness_to_pay: {willingness_to_pay}\n"
            f"- revenue_potential: {revenue_potential}\n"
            f"- problem_severity: {problem_severity}\n"
            f"- buildability: {buildability}\n"
            f"- system_fit: {system_fit}\n"
            f"- novelty: {novelty}\n"
            f"- **composite: {composite}**\n\n"
            f"## Problem\n{problem}\n\n## Who pays\n{who_pays}\n\n"
            f"## Build Spec\n_pending (P2)_\n\n## Sample Deliverable\n_pending (P2)_\n\n"
            f"## PoC Grade\n_pending (P3)_\n",
            encoding="utf-8",
        )
        return {"success": True, "slug": slug, "composite": composite}
    except OSError as exc:
        return {"error": str(exc)}


TOOL_SPEC_LOG = {
    "name": "log_opportunity",
    "description": (
        "Record a scored AI-agent business opportunity to the opportunity ledger and create its "
        "vault page. Call once per distinct idea you scout. Score each dimension 0-10. The composite "
        "(0-100) is computed for you. Dedupes by slug — never logs the same slug twice."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "kebab-case unique id, e.g. ai-review-reply-agent"},
            "one_liner": {"type": "string", "description": "One-sentence description"},
            "problem": {"type": "string", "description": "The pain this solves"},
            "who_pays": {"type": "string", "description": "Who the paying customer is"},
            "willingness_to_pay": {"type": "number", "description": "0-10: who pays & how much"},
            "revenue_potential": {"type": "number", "description": "0-10: ceiling if it works"},
            "problem_severity": {"type": "number", "description": "0-10: how real/painful"},
            "buildability": {"type": "number", "description": "0-10: inverse of build effort"},
            "system_fit": {"type": "number", "description": "0-10: can THIS system's agents/tools run it"},
            "novelty": {"type": "number", "description": "0-10: non-slop, defensible"},
            "est_rev_mo": {"type": "number", "description": "Estimated monthly revenue in USD (a hypothesis)"},
        },
        "required": [
            "slug", "one_liner", "problem", "who_pays",
            "willingness_to_pay", "revenue_potential", "problem_severity",
            "buildability", "system_fit", "novelty",
        ],
    },
}


_VALID_VERDICTS = {"promising", "weak", "dead"}


def grade_poc(slug: str, verdict: str, reason: str) -> dict:
    if verdict not in _VALID_VERDICTS:
        return {"error": f"verdict must be one of {sorted(_VALID_VERDICTS)}"}
    try:
        page = OPP_DIR / f"{slug}.md"
        if page.exists():
            text = page.read_text(encoding="utf-8")
            today = datetime.now().strftime("%Y-%m-%d")
            graded = text.replace(
                "## PoC Grade\n_pending (P3)_",
                f"## PoC Grade\n**{verdict}** ({today}) — {reason}",
            )
            if graded == text:  # already graded before; append
                graded = text + f"\n\n## PoC Grade ({today})\n**{verdict}** — {reason}\n"
            page.write_text(graded, encoding="utf-8")
        if LEDGER_FILE.exists():
            lines = LEDGER_FILE.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if line.startswith(f"| {slug} |"):
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    if len(cells) >= 9:
                        cells[2] = "graded"   # phase
                        cells[3] = verdict     # poc
                        cells[6] = "graded"    # status
                        cells[8] = datetime.now().strftime("%Y-%m-%d")
                        lines[i] = "| " + " | ".join(cells) + " |"
                    break
            LEDGER_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"success": True, "slug": slug, "verdict": verdict}
    except OSError as exc:
        return {"error": str(exc)}


def update_opportunity(
    slug: str,
    composite: float | None = None,
    phase: str | None = None,
    est_rev_mo: str | None = None,
    status: str | None = None,
) -> dict:
    """Update an existing ledger row in place — used after a deep-dive re-scores an
    idea, so the Opportunity Board reflects the revised composite/phase."""
    if not LEDGER_FILE.exists():
        return {"error": "ledger.md does not exist yet"}
    try:
        lines = LEDGER_FILE.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"| {slug} |"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 9:
                    return {"error": f"malformed ledger row for {slug}"}
                if composite is not None:
                    cells[1] = str(round(float(composite), 2))
                if phase is not None:
                    cells[2] = phase
                if est_rev_mo is not None:
                    cells[5] = str(est_rev_mo)
                if status is not None:
                    cells[6] = status
                cells[8] = datetime.now().strftime("%Y-%m-%d")
                lines[i] = "| " + " | ".join(cells) + " |"
                LEDGER_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return {"success": True, "slug": slug, "composite": cells[1], "phase": cells[2]}
        return {"error": f"{slug} not found in ledger"}
    except OSError as exc:
        return {"error": str(exc)}


TOOL_SPEC_UPDATE = {
    "name": "update_opportunity",
    "description": (
        "Update an existing opportunity's ledger row after a deep-dive re-scores it. "
        "ALWAYS call this at the end of a deep-dive with the revised composite and set "
        "phase to 'deepdived' so the Opportunity Board shows the evidence-based score, "
        "not the first-pass scout score. Only pass the fields you are changing."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "The opportunity slug exactly as in the ledger."},
            "composite": {"type": "number", "description": "Revised composite score 0-100."},
            "phase": {"type": "string", "description": "e.g. 'deepdived', 'graded', 'building'."},
            "est_rev_mo": {"type": "string", "description": "Estimated monthly revenue, if newly estimated."},
            "status": {"type": "string", "description": "e.g. 'deepdived', 'rejected', 'promoted'."},
        },
        "required": ["slug"],
    },
}


TOOL_SPEC_GRADE = {
    "name": "grade_poc",
    "description": (
        "Grade a proof-of-concept after reviewing its output under workspace/poc/<slug>/. "
        "verdict: promising = demo works and is worth scaling; weak = partial/unconvincing; "
        "dead = failed or no path. Updates the ledger and the opportunity page."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {"type": "string"},
            "verdict": {"type": "string", "enum": ["promising", "weak", "dead"]},
            "reason": {"type": "string", "description": "One paragraph justifying the verdict, citing the PoC output."},
        },
        "required": ["slug", "verdict", "reason"],
    },
}
