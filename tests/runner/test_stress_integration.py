"""Stress / robustness tests for the bot <-> command-center integration surface.

These exercise the failure modes a separate, concurrently-writing trading bot can inflict on
the CC: partial/truncated bridge writes, corrupt dedup logs, non-UTF8 bytes, malformed levels,
out-of-order intraday slots, over-capturing fan-out, racing task locks, and CRM rows whose
content collides with the parser. Each maps to a concrete bug fixed in this pass.
"""
import os
import threading

import pytest

from runner.bridge import tony_bridge as bridge
from runner.ledger import alpaca_paper as ap
from runner.tasks import locker


# --------------------------------------------------------------------------- bridge setup

def _bridge_setup(tmp_path, monkeypatch, quiesce=0.0):
    bridge_dir = tmp_path / "bridge" / "tony-stocks"
    tasks_dir = tmp_path / "workspace" / "tasks" / "todo"
    reports_dir = tmp_path / "reports"
    for d in (bridge_dir, tasks_dir, reports_dir):
        d.mkdir(parents=True)
    monkeypatch.setattr(bridge, "BRIDGE_MD_DIR", bridge_dir)
    monkeypatch.setattr(bridge, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(bridge, "TRADING_REPORTS_DIR", reports_dir)
    monkeypatch.setattr(bridge, "_PROCESSED_LOG", tmp_path / "processed.json")
    monkeypatch.setattr(bridge, "VAULT_DIR", tmp_path / "vault")
    monkeypatch.setattr(bridge, "_QUIESCE_SECONDS", quiesce)
    return bridge_dir, tasks_dir


_BODY = "## Tier 1\n### [[AAA]]\nDays active: 5\nScore: 88\nSetup: Breakout Watch\n"


def _write(bridge_dir, stem, body=_BODY):
    f = bridge_dir / f"{stem}.md"
    f.write_text(f"---\ndate: {stem[:10]}\n---\n\n{body}\n", encoding="utf-8")
    return f


# --------------------------------------------------------------------------- C1: quiescence gate

def test_fresh_bridge_skipped_until_quiesced(tmp_path, monkeypatch):
    bridge_dir, tasks_dir = _bridge_setup(tmp_path, monkeypatch, quiesce=30.0)
    f = _write(bridge_dir, "2026-06-05")
    # Just-written file (mtime = now) is within the quiesce window -> must NOT be ingested,
    # so a partial write can't be processed and permanently marked done.
    bridge.scan_and_process()
    assert not list(tasks_dir.glob("*.md"))
    # Age it past the window -> now it ingests.
    old = os.stat(f).st_mtime - 120
    os.utime(f, (old, old))
    bridge.scan_and_process()
    assert list(tasks_dir.glob("TONY-DAILY-BRIEF-*.md"))


# --------------------------------------------------------------------------- C2: per-key persist

def test_failing_bridge_does_not_block_or_dedup_others(tmp_path, monkeypatch):
    bridge_dir, tasks_dir = _bridge_setup(tmp_path, monkeypatch)
    _write(bridge_dir, "2026-06-05")            # good (newest, processed first)
    _write(bridge_dir, "2026-06-04T1030")       # will blow up

    real = bridge._make_intraday_brief

    def boom(slug, md):
        if slug == "2026-06-04T1030":
            raise RuntimeError("simulated mid-scan failure")
        return real(slug, md)

    monkeypatch.setattr(bridge, "_make_intraday_brief", boom)
    bridge.scan_and_process()  # must not raise despite the failing file

    processed = bridge._load_processed()
    assert "2026-06-05/daily_brief" in processed          # good one persisted per-key
    assert "2026-06-04T1030/brief" not in processed       # failed one left for retry
    assert list(tasks_dir.glob("TONY-DAILY-BRIEF-20260605.md"))


# --------------------------------------------------------------------------- C3: corrupt dedup log

def test_corrupt_processed_log_is_backed_up_not_silently_dropped(tmp_path, monkeypatch):
    _bridge_setup(tmp_path, monkeypatch)
    bridge._PROCESSED_LOG.write_text("{ this is not json", encoding="utf-8")
    assert bridge._load_processed() == set()                       # degrades, no crash
    assert bridge._PROCESSED_LOG.with_suffix(".json.corrupt").exists()  # preserved for inspection


def test_processed_log_save_is_atomic_roundtrip(tmp_path, monkeypatch):
    _bridge_setup(tmp_path, monkeypatch)
    bridge._save_processed({"a/brief", "b/brief"})
    assert bridge._load_processed() == {"a/brief", "b/brief"}
    assert not bridge._PROCESSED_LOG.with_suffix(".json.tmp").exists()  # tmp cleaned up


# --------------------------------------------------------------------------- M1: non-UTF8 input

def test_non_utf8_bridge_does_not_abort_scan(tmp_path, monkeypatch):
    bridge_dir, tasks_dir = _bridge_setup(tmp_path, monkeypatch)
    (bridge_dir / "2026-06-04.md").write_bytes(b"\xff\xfe garbage \x80\x81")
    _write(bridge_dir, "2026-06-05")  # newest, good
    bridge.scan_and_process()  # the bad-bytes file must not crash the whole scan
    assert list(tasks_dir.glob("TONY-DAILY-BRIEF-20260605.md"))


# --------------------------------------------------------------------------- H2: fan-out over-capture

def test_fanout_excludes_non_tier1_when_no_tier2(monkeypatch):
    md = (
        "## Tier 1\n### [[AAA]]\nScore 88\n### [[BBB]]\nScore 81\n"
        "## Scanner Watchlist\n### [[ZZZ]]\nwatching\n"  # must NOT be pulled into fan-out
    )
    assert bridge._extract_tier1_symbols(md) == ["AAA", "BBB"]


def test_fanout_ignores_tier1_mentioned_in_prose(monkeypatch):
    md = "Today we have 3 Tier 1 names.\n\n## Tier 1\n### [[AAA]]\n## Tier 2\n| [[QQQ]] | 70 |\n"
    assert bridge._extract_tier1_symbols(md) == ["AAA"]


# --------------------------------------------------------------------------- H3: intraday clobber

def test_intraday_slot_does_not_clobber_later_slot(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "VAULT_DIR", tmp_path / "vault")
    (tmp_path / "vault" / "tony-stocks").mkdir(parents=True)
    eod = "## Tier 1\n### [[EOD]]\nDays active: 5\nScore: 90\n"
    mid = "## Tier 1\n### [[MID]]\nDays active: 5\nScore: 70\n"
    # Newest-first ingestion after a restart: eod writes the ledger, then the older 15:30 runs.
    assert bridge._refresh_signal_ledger("2026-06-03Teod", eod) is True
    assert bridge._refresh_signal_ledger("2026-06-03T1530", mid) is False  # skipped, not backwards
    ledger = (tmp_path / "vault" / "tony-stocks" / "signal-ledger.md").read_text()
    assert "EOD" in ledger and "MID" not in ledger
    # A genuinely newer day still refreshes.
    assert bridge._refresh_signal_ledger("2026-06-04", "## Tier 1\n### [[NEW]]\nDays active: 5\n") is True


# --------------------------------------------------------------------------- ledger: malformed levels

def test_parse_scanner_levels_skips_malformed_block():
    md = (
        "### [[GOOD]]\nLast close: $50 | Target: $55.0 (+10%) | Stop: $48.0 (-4%)\n"
        "### [[BAD]]\nLast close: $50 | Target: $1.2.3 (+10%) | Stop: $48.0 (-4%)\n"
    )
    levels = ap.parse_scanner_levels(md)
    assert "GOOD" in levels and levels["GOOD"]["target"] == 55.0
    assert "BAD" not in levels  # malformed multi-dot number skipped, not a crash


# --------------------------------------------------------------------------- ledger: sizing boundaries

@pytest.mark.parametrize("price,expected", [(50.0, 200), (None, 1), (0, 1), (-5, 1)])
def test_whole_share_qty_boundaries(price, expected):
    assert ap.whole_share_qty(10000, price) == expected


def test_entry_qty_dollar_bounded_for_penny_price():
    # A penny price yields a huge share count but fixed-notional self-bounds dollar exposure.
    qty = ap.entry_qty(0.01)
    assert qty * 0.01 == pytest.approx(ap.ENTRY_NOTIONAL, rel=0.01)


# --------------------------------------------------------------------------- locker: race

def test_concurrent_lock_acquire_has_exactly_one_winner(tmp_path, monkeypatch):
    monkeypatch.setattr(locker, "LOCKS_DIR", tmp_path / "locks")
    results = []
    barrier = threading.Barrier(20)

    def grab():
        barrier.wait()  # maximize contention — all threads race the same instant
        results.append(locker.acquire_lock("TASK-1", "worker"))

    threads = [threading.Thread(target=grab) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for r in results if r) == 1  # exactly one winner despite 20 racers
