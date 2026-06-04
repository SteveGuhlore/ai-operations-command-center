from runner.ledger import equity_history as eh


def test_append_point_skips_empty_and_caps():
    pts = eh.append_point([], "t1", None, None)
    assert pts == []  # fully-empty snapshot is skipped
    pts = eh.append_point(pts, "t2", 1_000_000.0, 100_000.0)
    pts = eh.append_point(pts, "t3", 1_000_100.0, None)  # one side present -> kept
    assert len(pts) == 2
    capped = []
    for i in range(10):
        capped = eh.append_point(capped, f"t{i}", float(i + 1), None, max_points=3)
    assert len(capped) == 3 and capped[0]["tony"] == 8.0  # only the last 3 kept


def test_indexed_curve_normalizes_to_100():
    pts = [
        {"ts": "t1", "tony": 1_000_000.0, "bot": 100_000.0},
        {"ts": "t2", "tony": 1_010_000.0, "bot": 99_000.0},
    ]
    c = eh.indexed_curve(pts)
    assert c["points"][0] == {"ts": "t1", "tony": 100.0, "bot": 100.0}
    assert c["points"][1]["tony"] == 101.0 and c["points"][1]["bot"] == 99.0
    assert c["tony_return_pct"] == 1.0 and c["bot_return_pct"] == -1.0  # +1% vs -1%, capital-agnostic


def test_indexed_curve_handles_missing_side():
    pts = [{"ts": "t1", "tony": 1_000_000.0, "bot": None},
           {"ts": "t2", "tony": 1_005_000.0, "bot": None}]
    c = eh.indexed_curve(pts)
    assert c["points"][1]["tony"] == 100.5 and c["points"][1]["bot"] is None
    assert c["bot_return_pct"] is None


def test_indexed_curve_empty():
    c = eh.indexed_curve([])
    assert c["points"] == [] and c["tony_return_pct"] is None and c["bot_return_pct"] is None
