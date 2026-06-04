import json
from runner.ledger import tony_scorecard as sc


def _wire(tmp_path, monkeypatch, verdicts, outcomes):
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    (tmp_path / "o.json").write_text(json.dumps(outcomes))
    monkeypatch.setattr(sc, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(sc, "OUTCOMES_FILE", tmp_path / "o.json")


def test_scorecard_grades_and_matrix(tmp_path, monkeypatch):
    verdicts = [
        {"date": "2026-06-01", "symbol": "AAA", "tony_score": 80, "scanner_score": 75,
         "verdict": "reaffirm", "confidence": "high"},
        {"date": "2026-06-01", "symbol": "BBB", "tony_score": 30, "scanner_score": 78,
         "verdict": "override", "confidence": "high"},
    ]
    outcomes = [
        {"symbol": "AAA", "pick_date": "2026-06-01", "result": "target_hit", "return_pct": 12.0},
        {"symbol": "BBB", "pick_date": "2026-06-01", "result": "stop_hit", "return_pct": -9.0},
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = sc.compute_record()
    assert rec["graded"] == 2
    assert rec["tony_win_rate"] == 100.0  # reaffirm hit + override avoided a stop
    assert rec["agreement"]["override_saved"] == 1
    assert rec["agreement"]["agreed_right"] == 1
    assert rec["calibration"]["high"] == 100.0


def test_awaiting_when_no_outcomes(tmp_path, monkeypatch):
    (tmp_path / "v.json").write_text("[]")
    monkeypatch.setattr(sc, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(sc, "OUTCOMES_FILE", tmp_path / "missing.json")
    assert sc.compute_record()["status"] == "awaiting_outcomes"


def test_override_missed_counts(tmp_path, monkeypatch):
    verdicts = [{"date": "2026-06-01", "symbol": "AAA", "verdict": "override", "confidence": "low"}]
    outcomes = [{"symbol": "AAA", "pick_date": "2026-06-01", "return_pct": 8.0}]  # he was wrong to bail
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = sc.compute_record()
    assert rec["agreement"]["override_missed"] == 1
    assert rec["tony_win_rate"] == 0.0


def test_range_join_matches_tier1_verdict_after_first_appearance(tmp_path, monkeypatch):
    # Pick first appears 06-01 (Tier-3); Tony only verdicts on 06-03 (Tier-1); exits 06-09.
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "override", "confidence": "high"}]
    outcomes = [{"symbol": "AAA", "pick_date": "2026-06-01", "resolved_date": "2026-06-09",
                 "entry_date": "2026-06-04", "return_pct": -7.0}]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = sc.compute_record()
    assert rec["graded"] == 1
    assert rec["agreement"]["override_saved"] == 1  # he correctly bailed before the -7%


def test_pick_id_join_when_present(tmp_path, monkeypatch):
    verdicts = [{"date": "2026-06-03", "symbol": "AAA", "verdict": "reaffirm",
                 "pick_id": "AAA-2026-06-01", "confidence": "medium"}]
    outcomes = [{"symbol": "AAA", "pick_id": "AAA-2026-06-01", "return_pct": 6.0}]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    assert sc.compute_record()["tony_win_rate"] == 100.0


def test_write_record_mirrors_to_vault(tmp_path, monkeypatch):
    # Tony's weekly self-review reads vault/tony-stocks/tony_stocks_record.json; write_record
    # must put a copy there, not only in TradingBotAgentProject/reports.
    verdicts = [{"date": "2026-06-01", "symbol": "AAA", "verdict": "reaffirm", "confidence": "high"}]
    outcomes = [{"symbol": "AAA", "pick_date": "2026-06-01", "return_pct": 5.0}]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    reports_file = tmp_path / "reports" / "tony_stocks_record.json"
    vault_file = tmp_path / "vault" / "tony-stocks" / "tony_stocks_record.json"
    monkeypatch.setattr(sc, "RECORD_FILE", reports_file)
    monkeypatch.setattr(sc, "VAULT_RECORD_FILE", vault_file)

    rec = sc.write_record()

    assert rec["status"] == "scored"
    assert json.loads(reports_file.read_text()) == rec
    assert json.loads(vault_file.read_text()) == rec


def test_discover_edges_needs_min_n(tmp_path, monkeypatch):
    verdicts = [{"date": f"2026-06-0{i}", "symbol": "AAA", "verdict": "reaffirm",
                 "evidence": ["rev_growth"]} for i in range(1, 7)]
    outcomes = [{"symbol": "AAA", "pick_date": f"2026-06-0{i}", "return_pct": 5.0} for i in range(1, 7)]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    res = sc.discover_edges(min_n=5)
    assert res["status"] == "scored"
    assert res["edges"][0]["tag"] == "rev_growth"
    assert res["edges"][0]["win_rate"] == 100.0
