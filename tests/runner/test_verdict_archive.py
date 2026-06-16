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
    sc.VERDICTS_FILE.write_text(
        json.dumps(
            [
                {"date": "2026-06-10", "symbol": "NVDA", "verdict": "reaffirm"},
                {"date": "2026-06-10", "symbol": "AMD", "verdict": "pass"},
            ]
        )
    )
    assert sc.archive_verdicts() == {"archived": 2, "total": 2, "ok": True}
    sc.VERDICTS_FILE.write_text("[]")  # flush empties the live file

    # day 2: a new verdict; archive keeps day 1 AND adds day 2
    sc.VERDICTS_FILE.write_text(
        json.dumps([{"date": "2026-06-11", "symbol": "NVDA", "verdict": "adjust"}])
    )
    assert sc.archive_verdicts() == {"archived": 1, "total": 3, "ok": True}

    # _all_verdicts exposes the full history even though the live file holds only day 2
    keys = {(v["date"], v["symbol"]) for v in sc._all_verdicts()}
    assert keys == {
        ("2026-06-10", "NVDA"),
        ("2026-06-10", "AMD"),
        ("2026-06-11", "NVDA"),
    }


def test_compute_record_grades_off_archive_after_flush(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    # a verdict from a prior day, already flushed from the live file but kept in the archive
    sc.VERDICTS_ARCHIVE.write_text(
        json.dumps(
            [
                {
                    "date": "2026-06-09",
                    "symbol": "FOO",
                    "verdict": "reaffirm",
                    "confidence": "high",
                }
            ]
        )
    )
    sc.VERDICTS_FILE.write_text("[]")  # live file flushed
    sc.OUTCOMES_FILE.write_text(
        json.dumps(
            [
                {
                    "symbol": "FOO",
                    "pick_date": "2026-06-09",
                    "resolved_date": "2026-06-12",
                    "return_pct": 5.0,
                    "result": "target_hit",
                }
            ]
        )
    )
    rec = sc.compute_record()
    assert rec["status"] == "scored"
    assert rec["graded"] == 1  # graded off the ARCHIVE (live file is empty)
    assert rec["agreement"]["agreed_right"] == 1


def test_archive_dedups_latest_wins(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    sc.VERDICTS_ARCHIVE.write_text(
        json.dumps([{"date": "2026-06-10", "symbol": "X", "verdict": "pass"}])
    )
    sc.VERDICTS_FILE.write_text(
        json.dumps([{"date": "2026-06-10", "symbol": "X", "verdict": "override"}])
    )  # same day+symbol, newer call
    res = sc.archive_verdicts()
    assert res == {"archived": 0, "total": 1, "ok": True}  # replaced, not duplicated
    arch = json.loads(sc.VERDICTS_ARCHIVE.read_text())
    assert len(arch) == 1 and arch[0]["verdict"] == "override"


def test_corrupt_archive_recovers_from_backup(tmp_path, monkeypatch):
    # A good write leaves a .bak. If the primary later corrupts, the next archive recovers history
    # from the backup — it must NOT rebuild from today's live file only and wipe accumulated memory.
    _iso(tmp_path, monkeypatch)
    sc.VERDICTS_FILE.write_text(
        json.dumps(
            [
                {"date": "2026-06-10", "symbol": "NVDA", "verdict": "reaffirm"},
                {"date": "2026-06-10", "symbol": "AMD", "verdict": "pass"},
            ]
        )
    )
    assert sc.archive_verdicts()["ok"] is True
    assert sc._archive_sibling(".bak").exists()
    # corrupt the primary; live now holds only ONE new, different verdict
    sc.VERDICTS_ARCHIVE.write_text("{ not valid json ]")
    sc.VERDICTS_FILE.write_text(
        json.dumps([{"date": "2026-06-11", "symbol": "TSLA", "verdict": "adjust"}])
    )
    res = sc.archive_verdicts()
    assert res["ok"] is True
    keys = {
        (v["date"], v["symbol"]) for v in json.loads(sc.VERDICTS_ARCHIVE.read_text())
    }
    assert keys == {
        ("2026-06-10", "NVDA"),
        ("2026-06-10", "AMD"),
        ("2026-06-11", "TSLA"),
    }  # nothing lost
    assert sc._archive_sibling(
        ".corrupt"
    ).exists()  # bad file quarantined for inspection


def test_archive_write_is_atomic_with_backup(tmp_path, monkeypatch):
    _iso(tmp_path, monkeypatch)
    sc.VERDICTS_FILE.write_text(
        json.dumps([{"date": "2026-06-10", "symbol": "NVDA", "verdict": "reaffirm"}])
    )
    sc.archive_verdicts()
    assert sc.VERDICTS_ARCHIVE.exists() and sc._archive_sibling(".bak").exists()
    assert not sc._archive_sibling(
        ".tmp"
    ).exists()  # tmp swapped in atomically, never left behind


def _neuter_preopen(monkeypatch):
    """Stub the non-verdict steps of run_preopen_reset so the test isolates the flush gate."""
    from runner.ledger import research_queue
    from runner.bridge import tony_bridge
    from runner.scheduler import daily_jobs

    monkeypatch.delenv("TONY_NOTIFY", raising=False)
    monkeypatch.setattr(
        research_queue, "recheck_queue", lambda: {"validated": [], "discarded": []}
    )
    monkeypatch.setattr(tony_bridge, "make_preopen_deepdive", lambda *a, **k: None)
    monkeypatch.setattr(daily_jobs, "mark_preopen_ran", lambda *a, **k: None)


def test_preopen_skips_flush_when_archive_not_confirmed(tmp_path, monkeypatch):
    # The core safety: archiving not confirmed -> flush MUST NOT run (never delete unsaved verdicts).
    from runner.ledger import preopen, alpaca_paper

    _neuter_preopen(monkeypatch)
    flushed = {"n": 0}
    monkeypatch.setattr(
        sc, "archive_verdicts", lambda: {"archived": 0, "total": 5, "ok": False}
    )
    monkeypatch.setattr(
        alpaca_paper,
        "flush_session",
        lambda *a, **k: flushed.__setitem__("n", flushed["n"] + 1) or {},
    )
    summary = preopen.run_preopen_reset()
    assert flushed["n"] == 0
    assert summary["flush"].get("skipped") == "archive_not_confirmed"


def test_preopen_flushes_when_archive_confirmed(tmp_path, monkeypatch):
    from runner.ledger import preopen, alpaca_paper

    _neuter_preopen(monkeypatch)
    flushed = {"n": 0}
    monkeypatch.setattr(
        sc, "archive_verdicts", lambda: {"archived": 1, "total": 6, "ok": True}
    )
    monkeypatch.setattr(
        alpaca_paper,
        "flush_session",
        lambda *a, **k: flushed.__setitem__("n", flushed["n"] + 1) or {"cleared": 1},
    )
    preopen.run_preopen_reset()
    assert flushed["n"] == 1
