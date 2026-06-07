"""Walk-forward eval harness entrypoint (T1.1) — runs in the master-always-deployable gate.

Headless: `python evals/tony/walk_forward_eval.py` prints the baseline report + the fail-closed
promotion verdict and exits 0 when the HARNESS itself ran clean (exit 1 only on a harness error —
NOT on a refused promotion, which is the expected honest state while the realized sample is thin).
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from runner.eval import harness


def run() -> dict:
    return harness.run()


if __name__ == "__main__":
    r = run()
    summary = {k: v for k, v in r.items() if k != "report"}
    print(json.dumps(summary, indent=2, default=str))
    raise SystemExit(0 if r.get("ok") else 1)
