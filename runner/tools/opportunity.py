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
