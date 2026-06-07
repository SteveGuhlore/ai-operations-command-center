"""walk_forward — leakage-safe temporal splits over delayed labels.

The whole point of the harness: NEVER train on the future. Picks are ordered by `resolved_date`
(when the label became known) and split into expanding-window folds — each fold trains on
everything resolved before a cutoff and tests on a held-out future block. Fold boundaries SNAP so a
single resolution date never straddles train and test (no same-day leakage). The pooled test set
across folds is the true out-of-sample sample the promotion gate reads.
"""
from runner.eval import data_contract, metrics


def _snap_boundaries(ordered: list, n_folds: int, min_train_frac: float) -> list:
    """Return test-block start indices, snapped to resolution-date edges so no date straddles a
    train/test boundary. The region before the first boundary is the initial training window."""
    n = len(ordered)
    if n < 2:
        return []
    start = max(1, int(n * min_train_frac))
    dates = [str(p.get("resolved_date") or "") for p in ordered]

    def snap_forward(i: int) -> int:
        # advance to the first index whose date differs from i-1's (don't split within a date)
        while 0 < i < n and dates[i] == dates[i - 1]:
            i += 1
        return i

    start = snap_forward(start)
    if start >= n:  # everything shares too few distinct dates — one big test block
        start = snap_forward(1)
        return [start] if start < n else []
    bounds = []
    span = n - start
    step = max(1, span // max(1, n_folds))
    i = start
    while i < n:
        bounds.append(i)
        i = snap_forward(i + step)
    return bounds


def folds(picks: list, n_folds: int = 3, min_train_frac: float = 0.4) -> list:
    """Expanding-window folds: [{cutoff, train, test}]. train = all picks resolved before the test
    block; test = the next contiguous block. Empty when there isn't enough history for one split."""
    ordered = data_contract.order_by_resolution(picks)
    bounds = _snap_boundaries(ordered, n_folds, min_train_frac)
    out = []
    for bi, b in enumerate(bounds):
        end = bounds[bi + 1] if bi + 1 < len(bounds) else len(ordered)
        test = ordered[b:end]
        if not test:
            continue
        out.append({"cutoff": str(ordered[b - 1].get("resolved_date")) if b > 0 else None,
                    "train": ordered[:b], "test": test})
    return out


def evaluate(picks: list, n_folds: int = 3, min_train_frac: float = 0.4) -> dict:
    """Walk-forward out-of-sample metrics. The POOLED test set (every held-out pick, each graded by
    a model that only saw its past) is the headline; per-fold figures show stability. Reports an
    explicit status when history is too thin to split — fail-loud, never a fake number."""
    fs = folds(picks, n_folds, min_train_frac)
    if not fs:
        return {"status": "insufficient_history", "folds": 0,
                "oos": {"win_rate": metrics.win_rate([]), "expectancy_return": metrics.expectancy_return([])},
                "per_fold": []}
    pooled_test: list = []
    per_fold = []
    for i, f in enumerate(fs):
        pooled_test.extend(f["test"])
        per_fold.append({
            "fold": i,
            "cutoff": f["cutoff"],
            "n_train": len(f["train"]),
            "n_test": len(f["test"]),
            "win_rate": metrics.win_rate(f["test"]),
            "expectancy_return": metrics.expectancy_return(f["test"]),
        })
    return {
        "status": "scored",
        "folds": len(fs),
        "oos": {
            "n": len(pooled_test),
            "win_rate": metrics.win_rate(pooled_test),
            "expectancy_return": metrics.expectancy_return(pooled_test),
            "expectancy_r": metrics.expectancy_r(pooled_test),
            "calibration": metrics.calibration(pooled_test),
        },
        "per_fold": per_fold,
    }
