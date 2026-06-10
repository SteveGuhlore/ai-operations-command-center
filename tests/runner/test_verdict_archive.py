"""Verdict learning-archive: the daily flush wipes the live verdicts file (needed for execution),
so the scorecard must grade off a persistent archive UNION the live file — otherwise verdict->outcome
learning stays starved (graded stuck at ~2)."""
import json

from runner.ledger import tony_scorecard as sc


def _iso(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "VERDICTS_FILE", tmp_path / "verdicts.json")
    monkeypatch.setattr(sc, "VERDICTS_ARCHIVE", tmp_path / "archive.json")
    monkeypatch.setattr(sc, "OUTCOMES_FILE", tmp_path / "outcomes.json")


def test_archive_accumulates_across_flushes(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    # day 1: two verdicts, then flush archives them
    sc.VERDICTS_FILE.write_text(json.dumps([
        {"date": "2026-06-10", "symbol": "NVDA", "verdict": "reaffirm"},
        {"date": "2026-06-10", "symbol": "AMD", "verdict": "pass"}]))
    assert sc.archive_verdicts() == {"archived": 2, "total": 2}
    sc.VERDICTS_FILE.write_text("[]")  # flush empties the live file

    # day 2: a new verdict; archive keeps day 1 AND adds day 2
    sc.VERDICTS_FILE.write_text(json.dumps([{"date": "2026-06-11", "symbol": "NVDA", "verdict": "adjust"}]))
    assert sc.archive_verdicts() == {"archived": 1, "total": 3}

    # _all_verdicts exposes the full history even though the live file holds only day 2
    keys = {(v["date"], v["symbol"]) for v in sc._all_verdicts()}
    assert keys == {("2026-06-10", "NVDA"), ("2026-06-10", "AMD"), ("2026-06-11", "NVDA")}


def test_compute_record_grades_off_archive_after_flush(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    # a verdict from a prior day, already flushed from the live file but kept in the archive
    sc.VERDICTS_ARCHIVE.write_text(json.dumps([
        {"date": "2026-06-09", "symbol": "FOO", "verdict": "reaffirm", "confidence": "high"}]))
    sc.VERDICTS_FILE.write_text("[]")  # live file flushed
    sc.OUTCOMES_FILE.write_text(json.dumps([
        {"symbol": "FOO", "pick_date": "2026-06-09", "resolved_date": "2026-06-12",
         "return_pct": 5.0, "result": "target_hit"}]))
    rec = sc.compute_record()
    assert rec["status"] == "scored"
    assert rec["graded"] == 1                    # graded off the ARCHIVE (live file is empty)
    assert rec["agreement"]["agreed_right"] == 1


def test_archive_dedups_latest_wins(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    sc.VERDICTS_ARCHIVE.write_text(json.dumps([
        {"date": "2026-06-10", "symbol": "X", "verdict": "pass"}]))
    sc.VERDICTS_FILE.write_text(json.dumps([
        {"date": "2026-06-10", "symbol": "X", "verdict": "override"}]))  # same day+symbol, newer call
    res = sc.archive_verdicts()
    assert res == {"archived": 0, "total": 1}     # replaced, not duplicated
    arch = json.loads(sc.VERDICTS_ARCHIVE.read_text())
    assert len(arch) == 1 and arch[0]["verdict"] == "override"
