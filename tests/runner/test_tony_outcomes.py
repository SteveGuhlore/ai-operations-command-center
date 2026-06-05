import json

from runner.tools import tony_outcomes as to


def _wire(tmp_path, monkeypatch, verdicts, outcomes):
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    (tmp_path / "o.json").write_text(json.dumps(outcomes))
    monkeypatch.setenv("TONY_VERDICTS_FILE", str(tmp_path / "v.json"))
    monkeypatch.setenv("TONY_OUTCOMES_FILE", str(tmp_path / "o.json"))


def test_awaiting_when_no_outcomes(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch, verdicts=[], outcomes=[])
    rec = to.get_tony_outcomes()
    assert rec["status"] == "awaiting_outcomes"
    block = to.track_record_block()
    assert "Awaiting resolved outcomes" in block
    assert block.startswith("## Your Track Record")


def test_scanner_base_rate_computed_without_verdicts(tmp_path, monkeypatch):
    # Outcomes exist but Tony has no matching verdicts yet — base rate should still populate.
    outcomes = [
        {"symbol": "AAA", "pick_date": "2026-05-18", "result": "target_hit", "return_pct": 10.0, "days_held": 8},
        {"symbol": "BBB", "pick_date": "2026-05-18", "result": "stop_hit", "return_pct": -5.0, "days_held": 12},
        {"symbol": "CCC", "pick_date": "2026-05-18", "result": "stop_hit", "return_pct": None, "days_held": None},
    ]
    _wire(tmp_path, monkeypatch, verdicts=[], outcomes=outcomes)
    rec = to.get_tony_outcomes()
    assert rec["status"] == "scored"
    sb = rec["scanner_base"]
    assert sb["resolved"] == 3
    assert sb["with_return"] == 2          # null-return pick excluded from the rate
    assert sb["pct_positive"] == 50.0      # 1 of 2 green
    assert sb["avg_return_pct"] == 2.5     # (10 + -5) / 2
    assert sb["by_result"]["stop_hit"] == 2
    assert rec["tony"]["graded"] == 0      # nothing matched


def test_per_verdict_winrate_expectancy_and_r(tmp_path, monkeypatch):
    verdicts = [
        # reaffirm a winner -> right; R = (110-100)/(100-90) = +1.0
        {"date": "2026-06-01", "symbol": "WIN", "verdict": "reaffirm", "stop": 90.0,
         "confidence": "high", "evidence": ["clean_breakout"]},
        # reaffirm a loser -> wrong; R = (95-100)/(100-90) = -0.5
        {"date": "2026-06-01", "symbol": "LOSE", "verdict": "reaffirm", "stop": 90.0,
         "confidence": "low", "evidence": ["clean_breakout"]},
        # override a loser -> right (correctly stepped off)
        {"date": "2026-06-01", "symbol": "AVOID", "verdict": "override", "stop": 90.0,
         "confidence": "high", "evidence": ["earnings_in_window"]},
    ]
    outcomes = [
        {"symbol": "WIN", "pick_date": "2026-06-01", "result": "target_hit",
         "entry": 100.0, "exit": 110.0, "return_pct": 10.0},
        {"symbol": "LOSE", "pick_date": "2026-06-01", "result": "stop_hit",
         "entry": 100.0, "exit": 95.0, "return_pct": -5.0},
        {"symbol": "AVOID", "pick_date": "2026-06-01", "result": "stop_hit",
         "entry": 100.0, "exit": 95.0, "return_pct": -5.0},
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = to.get_tony_outcomes()
    t = rec["tony"]
    assert t["graded"] == 3
    # reaffirm: 1 right of 2 = 50%; override: 1 right of 1 = 100%; overall 2/3
    assert t["win_rate"] == 66.7
    assert t["by_verdict"]["reaffirm"]["win_rate"] == 50.0
    assert t["by_verdict"]["reaffirm"]["avg_r"] == 0.25      # (+1.0 + -0.5) / 2
    assert t["by_verdict"]["override"]["win_rate"] == 100.0
    # expectancy = mean return across all graded = (10 -5 -5)/3
    assert t["expectancy_pct"] == 0.0
    # calibration: high bucket = WIN(right)+AVOID(right) = 100%, low = LOSE(wrong) = 0%
    assert t["calibration"]["high"] == 100.0
    assert t["calibration"]["low"] == 0.0


def test_edges_respect_min_samples(tmp_path, monkeypatch):
    verdicts = [
        {"date": "2026-06-01", "symbol": f"S{i}", "verdict": "reaffirm", "stop": 90.0,
         "confidence": "medium", "evidence": ["hot_tag"]}
        for i in range(4)
    ]
    outcomes = [
        {"symbol": f"S{i}", "pick_date": "2026-06-01", "result": "target_hit", "return_pct": 5.0}
        for i in range(4)
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = to.get_tony_outcomes(min_edge_samples=3)
    assert rec["tony"]["best_setups"] == [{"tag": "hot_tag", "n": 4, "win_rate": 100.0}]
    # raise the bar above the sample count -> no edge survives
    assert to.get_tony_outcomes(min_edge_samples=5)["tony"]["best_setups"] == []


def test_block_renders_scored_summary(tmp_path, monkeypatch):
    verdicts = [
        {"date": "2026-06-01", "symbol": "WIN", "verdict": "reaffirm", "stop": 90.0,
         "confidence": "high", "evidence": ["clean_breakout"]},
    ]
    outcomes = [
        {"symbol": "WIN", "pick_date": "2026-06-01", "result": "target_hit",
         "entry": 100.0, "exit": 110.0, "return_pct": 10.0, "days_held": 6},
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    block = to.track_record_block()
    assert "Scanner base rate" in block
    assert "Your graded calls" in block
    assert "win-rate 100.0%" in block


def test_default_paths_resolve_to_sibling_bot_repo():
    # Guard the cross-repo default so a future move doesn't silently break the join.
    assert to._outcomes_path().name == "tony_stocks_outcomes.json"
    assert to._outcomes_path().parent.name == "reports"
    assert to._outcomes_path().parent.parent.name == "TradingBotAgentProject"
