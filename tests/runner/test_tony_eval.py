from evals.tony import run_eval


def test_grading_logic_regression():
    r = run_eval.run()
    assert r["ok"], f"grading-rule regression: {r['failures']}"
    assert r["passed"] >= 9
