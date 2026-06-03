"""Verdict-logic regression eval — guards Tony's grading/agreement math.

The scorecard's grading rule decides whether Tony "beat the scanner." If a future prompt
or refactor silently flips that logic, the whole learning loop becomes garbage. This eval
locks the rule down with fixed cases (no network). Run headless: `python evals/tony/run_eval.py`.
"""
import json
from pathlib import Path

from runner.ledger import tony_scorecard as sc

FIXTURES = Path(__file__).parent / "fixtures.json"


def run() -> dict:
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
    passed = failed = 0
    failures = []
    for c in cases:
        got = sc._is_right(c["verdict"], c["return_pct"])
        if got == c["expected_right"]:
            passed += 1
        else:
            failed += 1
            failures.append({**c, "got": got})
    return {"passed": passed, "failed": failed, "ok": failed == 0, "failures": failures}


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["ok"] else 1)
