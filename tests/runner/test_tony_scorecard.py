import json
from runner.ledger import tony_scorecard as sc


def _wire(tmp_path, monkeypatch, verdicts, outcomes):
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    (tmp_path / "o.json").write_text(json.dumps(outcomes))
    monkeypatch.setattr(sc, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(sc, "OUTCOMES_FILE", tmp_path / "o.json")
    monkeypatch.setattr(sc, "VERDICTS_ARCHIVE", tmp_path / "varch.json")
    monkeypatch.setattr(sc, "GRADED_ARCHIVE", tmp_path / "graded.json")


def test_scorecard_grades_and_matrix(tmp_path, monkeypatch):
    verdicts = [
        {
            "date": "2026-06-01",
            "symbol": "AAA",
            "tony_score": 80,
            "scanner_score": 75,
            "verdict": "reaffirm",
            "confidence": "high",
        },
        {
            "date": "2026-06-01",
            "symbol": "BBB",
            "tony_score": 30,
            "scanner_score": 78,
            "verdict": "override",
            "confidence": "high",
        },
    ]
    outcomes = [
        {
            "symbol": "AAA",
            "pick_date": "2026-06-01",
            "result": "target_hit",
            "return_pct": 12.0,
        },
        {
            "symbol": "BBB",
            "pick_date": "2026-06-01",
            "result": "stop_hit",
            "return_pct": -9.0,
        },
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = sc.compute_record()
    assert rec["graded"] == 2
    assert (
        rec["win_rate"] == 100.0 == rec["tony_win_rate"]
    )  # reaffirm hit + override avoided a stop
    assert rec["agreement"]["cc_overrode_saved"] == 1
    assert rec["agreement"]["agreed_right"] == 1
    assert rec["calibration"]["high"] == 100.0
    assert rec["target_hits"] == 1 and rec["stop_hits"] == 1
    assert rec["avg_pl_per_trade"] == 1.5  # mean(12.0, -9.0)


def test_awaiting_when_no_outcomes(tmp_path, monkeypatch):
    (tmp_path / "v.json").write_text("[]")
    monkeypatch.setattr(sc, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(sc, "OUTCOMES_FILE", tmp_path / "missing.json")
    assert sc.compute_record()["status"] == "awaiting_outcomes"


def test_override_missed_counts(tmp_path, monkeypatch):
    verdicts = [
        {
            "date": "2026-06-01",
            "symbol": "AAA",
            "verdict": "override",
            "confidence": "low",
        }
    ]
    outcomes = [
        {"symbol": "AAA", "pick_date": "2026-06-01", "return_pct": 8.0}
    ]  # he was wrong to bail
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = sc.compute_record()
    assert rec["agreement"]["cc_overrode_missed"] == 1
    assert rec["tony_win_rate"] == 0.0


def test_range_join_matches_tier1_verdict_after_first_appearance(tmp_path, monkeypatch):
    # Pick first appears 06-01 (Tier-3); Tony only verdicts on 06-03 (Tier-1); exits 06-09.
    verdicts = [
        {
            "date": "2026-06-03",
            "symbol": "AAA",
            "verdict": "override",
            "confidence": "high",
        }
    ]
    outcomes = [
        {
            "symbol": "AAA",
            "pick_date": "2026-06-01",
            "resolved_date": "2026-06-09",
            "entry_date": "2026-06-04",
            "return_pct": -7.0,
        }
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = sc.compute_record()
    assert rec["graded"] == 1
    assert (
        rec["agreement"]["cc_overrode_saved"] == 1
    )  # he correctly bailed before the -7%


def test_pick_id_join_when_present(tmp_path, monkeypatch):
    verdicts = [
        {
            "date": "2026-06-03",
            "symbol": "AAA",
            "verdict": "reaffirm",
            "pick_id": "AAA-2026-06-01",
            "confidence": "medium",
        }
    ]
    outcomes = [{"symbol": "AAA", "pick_id": "AAA-2026-06-01", "return_pct": 6.0}]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    assert sc.compute_record()["tony_win_rate"] == 100.0


def test_write_record_mirrors_to_vault(tmp_path, monkeypatch):
    # Tony's weekly self-review reads vault/tony-stocks/tony_stocks_record.json; write_record
    # must put a copy there, not only in TradingBotAgentProject/reports.
    verdicts = [
        {
            "date": "2026-06-01",
            "symbol": "AAA",
            "verdict": "reaffirm",
            "confidence": "high",
        }
    ]
    outcomes = [{"symbol": "AAA", "pick_date": "2026-06-01", "return_pct": 5.0}]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    reports_file = tmp_path / "reports" / "tony_stocks_record.json"
    vault_file = tmp_path / "vault" / "tony-stocks" / "tony_stocks_record.json"
    monkeypatch.setattr(sc, "RECORD_FILE", reports_file)
    monkeypatch.setattr(sc, "VAULT_RECORD_FILE", vault_file)
    monkeypatch.setattr(
        sc, "_tony_equity_curve", lambda: []
    )  # isolate from the real equity history

    rec = sc.write_record()

    assert rec["status"] == "scored"
    assert json.loads(reports_file.read_text()) == rec
    assert json.loads(vault_file.read_text()) == rec


def test_record_full_schema_for_bot_reader(tmp_path, monkeypatch):
    # The bot's CommandCenterAgreement + record reader require this exact shape.
    verdicts = [
        {
            "date": "2026-06-01",
            "symbol": "AAA",
            "verdict": "reaffirm",
            "confidence": "high",
        }
    ]
    outcomes = [
        {
            "symbol": "AAA",
            "pick_date": "2026-06-01",
            "result": "target_hit",
            "return_pct": 5.0,
        }
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    monkeypatch.setattr(sc, "RECORD_FILE", tmp_path / "rec.json")
    monkeypatch.setattr(sc, "VAULT_RECORD_FILE", tmp_path / "vrec.json")
    monkeypatch.setattr(sc, "_tony_equity_curve", lambda: [100.0, 101.5, 103.2])
    rec = sc.write_record()
    for k in (
        "win_rate",
        "avg_pl_per_trade",
        "target_hits",
        "stop_hits",
        "equity_curve",
        "agreement",
    ):
        assert k in rec
    assert rec["equity_curve"] == [100.0, 101.5, 103.2]
    assert set(rec["agreement"]) == {
        "agreed_right",
        "agreed_wrong",
        "cc_overrode_saved",
        "cc_overrode_missed",
    }


def test_awaiting_record_has_full_schema(tmp_path, monkeypatch):
    (tmp_path / "v.json").write_text("[]")
    monkeypatch.setattr(sc, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(sc, "OUTCOMES_FILE", tmp_path / "missing.json")
    rec = sc.compute_record()
    assert rec["status"] == "awaiting_outcomes"
    for k in (
        "win_rate",
        "avg_pl_per_trade",
        "target_hits",
        "stop_hits",
        "agreement",
        "calibration",
    ):
        assert k in rec
    assert set(rec["agreement"]) == {
        "agreed_right",
        "agreed_wrong",
        "cc_overrode_saved",
        "cc_overrode_missed",
    }


def test_discover_edges_needs_min_n(tmp_path, monkeypatch):
    verdicts = [
        {
            "date": f"2026-06-0{i}",
            "symbol": "AAA",
            "verdict": "reaffirm",
            "evidence": ["rev_growth"],
        }
        for i in range(1, 7)
    ]
    outcomes = [
        {"symbol": "AAA", "pick_date": f"2026-06-0{i}", "return_pct": 5.0}
        for i in range(1, 7)
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    res = sc.discover_edges(min_n=5)
    assert res["status"] == "scored"
    assert res["edges"][0]["tag"] == "rev_growth"
    assert res["edges"][0]["win_rate"] == 100.0


def test_grades_verdict_issued_after_pick_resolved(tmp_path, monkeypatch):
    # Fast stop-out: the pick resolved 06-02, but Tony only reviewed it 06-04 (late fan-out /
    # cooldown). The old [pick_date, resolved_date] join silently DROPPED this from the tally;
    # now it still grades, which is what closes the 34-vs-52 gap on the "2nd pass" panel.
    verdicts = [
        {
            "date": "2026-06-04",
            "symbol": "AAA",
            "verdict": "reaffirm",
            "confidence": "high",
        }
    ]
    outcomes = [
        {
            "symbol": "AAA",
            "pick_date": "2026-06-01",
            "resolved_date": "2026-06-02",
            "result": "stop_hit",
            "return_pct": -4.0,
        }
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = sc.compute_record()
    assert rec["graded"] == 1
    assert rec["agreement"]["agreed_wrong"] == 1  # he backed it; it lost


def test_repick_verdict_attributed_to_later_episode(tmp_path, monkeypatch):
    # AAA picked twice. A verdict dated 06-09 reviews the 06-08 RE-pick — the next-episode
    # bound must keep it from being stolen by the already-resolved 06-01 episode.
    verdicts = [
        {
            "date": "2026-06-02",
            "symbol": "AAA",
            "verdict": "reaffirm",
        },  # reviews episode 1
        {
            "date": "2026-06-09",
            "symbol": "AAA",
            "verdict": "override",
        },  # reviews episode 2
    ]
    outcomes = [
        {
            "symbol": "AAA",
            "pick_date": "2026-06-01",
            "result": "target_hit",
            "return_pct": 6.0,
        },
        {
            "symbol": "AAA",
            "pick_date": "2026-06-08",
            "result": "stop_hit",
            "return_pct": -5.0,
        },
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    rec = sc.compute_record()
    assert rec["graded"] == 2
    assert rec["agreement"]["agreed_right"] == 1  # episode 1: reaffirm + win
    assert rec["agreement"]["cc_overrode_saved"] == 1  # episode 2: override + loss


def test_published_record_is_monotonic(tmp_path, monkeypatch):
    # The published record (write_record) must never shrink, even when a later recompute can no
    # longer re-match an already-graded pick (verdict rotated out, outcome dropped, date skew).
    verdicts = [
        {
            "date": "2026-06-01",
            "symbol": "AAA",
            "verdict": "reaffirm",
            "confidence": "high",
        }
    ]
    outcomes = [
        {
            "symbol": "AAA",
            "pick_date": "2026-06-01",
            "result": "target_hit",
            "return_pct": 5.0,
        }
    ]
    _wire(tmp_path, monkeypatch, verdicts, outcomes)
    monkeypatch.setattr(sc, "RECORD_FILE", tmp_path / "rec.json")
    monkeypatch.setattr(sc, "VAULT_RECORD_FILE", tmp_path / "vrec.json")
    monkeypatch.setattr(sc, "_tony_equity_curve", lambda: [])

    rec1 = sc.write_record()
    assert rec1["graded"] == 1 and rec1["agreement"]["agreed_right"] == 1

    # Next run: AAA's verdict is gone everywhere, but a new BBB pick resolves.
    sc.VERDICTS_FILE.write_text(
        json.dumps(
            [
                {
                    "date": "2026-06-08",
                    "symbol": "BBB",
                    "verdict": "reaffirm",
                    "confidence": "high",
                }
            ]
        )
    )
    sc.VERDICTS_ARCHIVE.write_text("[]")
    sc.OUTCOMES_FILE.write_text(
        json.dumps(
            [
                {
                    "symbol": "AAA",
                    "pick_date": "2026-06-01",
                    "result": "target_hit",
                    "return_pct": 5.0,
                },
                {
                    "symbol": "BBB",
                    "pick_date": "2026-06-08",
                    "result": "target_hit",
                    "return_pct": 3.0,
                },
            ]
        )
    )
    rec2 = sc.write_record()
    assert rec2["graded"] == 2  # grew (AAA locked + BBB new), did NOT shrink
    assert rec2["agreement"]["agreed_right"] == 2
    # The fresh, non-monotonic view DOES lose AAA — proving the archive is what retains it.
    assert sc.compute_record()["graded"] == 1
