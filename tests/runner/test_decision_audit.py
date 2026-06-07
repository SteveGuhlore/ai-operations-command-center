import json
import os

import pytest

import runner.ledger.decision_audit as da


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redirect(monkeypatch, tmp_path):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", str(path))
    return path


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# record_decision
# ---------------------------------------------------------------------------

def test_record_decision_writes_one_line(tmp_path, monkeypatch):
    path = _redirect(monkeypatch, tmp_path)
    rec = da.record_decision("verdict", symbol="AAPL", confidence="high", score=82)
    assert path.exists()
    lines = _lines(path)
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["kind"] == "verdict"
    assert parsed["symbol"] == "AAPL"
    assert parsed["confidence"] == "high"
    assert parsed["score"] == 82
    assert "ts" in parsed
    assert "date" in parsed
    assert len(parsed["date"]) == 10  # YYYY-MM-DD


def test_record_decision_returns_written_record(tmp_path, monkeypatch):
    _redirect(monkeypatch, tmp_path)
    rec = da.record_decision("order", symbol="TSLA", qty=10, side="buy")
    assert rec is not None
    assert rec["kind"] == "order"
    assert rec["symbol"] == "TSLA"
    assert rec["qty"] == 10
    assert rec["side"] == "buy"
    assert "ts" in rec and "date" in rec


def test_record_decision_appends_second_call(tmp_path, monkeypatch):
    path = _redirect(monkeypatch, tmp_path)
    da.record_decision("verdict", symbol="AAPL")
    da.record_decision("skip", symbol="GOOG", reason="low_score")
    lines = _lines(path)
    assert len(lines) == 2
    assert json.loads(lines[0])["kind"] == "verdict"
    assert json.loads(lines[1])["kind"] == "skip"
    assert json.loads(lines[1])["reason"] == "low_score"


def test_record_decision_symbol_none(tmp_path, monkeypatch):
    path = _redirect(monkeypatch, tmp_path)
    rec = da.record_decision("breaker", detail="market_halt")
    assert rec["symbol"] is None
    assert json.loads(_lines(path)[0])["symbol"] is None


def test_record_decision_unwritable_path_returns_none(tmp_path, monkeypatch):
    # Use an existing regular file as the parent directory — mkdir will fail on any OS
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    bad_path = blocker / "audit.jsonl"  # parent is a file, not a dir
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", str(bad_path))
    result = da.record_decision("verdict", symbol="AAPL")
    assert result is None  # fail-soft: never raises


def test_record_decision_does_not_raise_on_bad_path(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("x", encoding="utf-8")
    bad_path = blocker / "audit.jsonl"
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", str(bad_path))
    try:
        da.record_decision("verdict", symbol="AAPL")
    except Exception as exc:
        pytest.fail(f"record_decision raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# read_decisions
# ---------------------------------------------------------------------------

def test_read_decisions_returns_all(tmp_path, monkeypatch):
    path = _redirect(monkeypatch, tmp_path)
    da.record_decision("verdict", symbol="AAPL")
    da.record_decision("order", symbol="TSLA")
    recs = da.read_decisions()
    assert len(recs) == 2


def test_read_decisions_filter_by_kind(tmp_path, monkeypatch):
    _redirect(monkeypatch, tmp_path)
    da.record_decision("verdict", symbol="AAPL")
    da.record_decision("skip", symbol="GOOG")
    da.record_decision("verdict", symbol="MSFT")
    recs = da.read_decisions(kind="verdict")
    assert len(recs) == 2
    assert all(r["kind"] == "verdict" for r in recs)


def test_read_decisions_filter_by_since(tmp_path, monkeypatch):
    path = _redirect(monkeypatch, tmp_path)
    # Write two records with distinct timestamps by injecting raw lines
    early = {"ts": "2026-01-01T00:00:00+00:00", "date": "2026-01-01", "kind": "verdict", "symbol": "A"}
    late  = {"ts": "2026-06-01T00:00:00+00:00", "date": "2026-06-01", "kind": "verdict", "symbol": "B"}
    path.write_text(json.dumps(early) + "\n" + json.dumps(late) + "\n", encoding="utf-8")
    recs = da.read_decisions(since="2026-03-01")
    assert len(recs) == 1
    assert recs[0]["symbol"] == "B"


def test_read_decisions_limit_returns_most_recent_n(tmp_path, monkeypatch):
    _redirect(monkeypatch, tmp_path)
    for i in range(5):
        da.record_decision("verdict", symbol=f"SYM{i}")
    recs = da.read_decisions(limit=3)
    assert len(recs) == 3
    # Last 3 written are the most recent — symbols 2, 3, 4
    symbols = [r["symbol"] for r in recs]
    assert "SYM2" in symbols
    assert "SYM3" in symbols
    assert "SYM4" in symbols


def test_read_decisions_skips_malformed_lines(tmp_path, monkeypatch):
    path = _redirect(monkeypatch, tmp_path)
    good = {"ts": "2026-06-01T00:00:00+00:00", "date": "2026-06-01", "kind": "verdict", "symbol": "A"}
    path.write_text("NOT JSON AT ALL\n" + json.dumps(good) + "\n", encoding="utf-8")
    recs = da.read_decisions()
    assert len(recs) == 1
    assert recs[0]["symbol"] == "A"


def test_read_decisions_returns_empty_on_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", str(tmp_path / "nonexistent.jsonl"))
    recs = da.read_decisions()
    assert recs == []


def test_read_decisions_does_not_raise_on_bad_path(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", str(tmp_path / "nonexistent_subdir" / "audit.jsonl"))
    try:
        result = da.read_decisions()
        assert result == []
    except Exception as exc:
        pytest.fail(f"read_decisions raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

def test_summary_counts_by_kind_and_date(tmp_path, monkeypatch):
    path = _redirect(monkeypatch, tmp_path)
    rows = [
        {"ts": "2026-06-01T09:00:00+00:00", "date": "2026-06-01", "kind": "verdict", "symbol": "A"},
        {"ts": "2026-06-01T10:00:00+00:00", "date": "2026-06-01", "kind": "order",   "symbol": "A"},
        {"ts": "2026-06-02T09:00:00+00:00", "date": "2026-06-02", "kind": "verdict", "symbol": "B"},
        {"ts": "2026-06-02T10:00:00+00:00", "date": "2026-06-02", "kind": "skip",    "symbol": "C"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    s = da.summary()
    assert s["total"] == 4
    assert s["by_kind"]["verdict"] == 2
    assert s["by_kind"]["order"] == 1
    assert s["by_kind"]["skip"] == 1
    assert s["by_date"]["2026-06-01"] == 2
    assert s["by_date"]["2026-06-02"] == 2


def test_summary_empty_file(tmp_path, monkeypatch):
    _redirect(monkeypatch, tmp_path)
    s = da.summary()
    assert s == {"total": 0, "by_kind": {}, "by_date": {}}


def test_summary_does_not_raise_on_bad_path(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", str(tmp_path / "nonexistent_subdir" / "audit.jsonl"))
    try:
        s = da.summary()
        assert s["total"] == 0
    except Exception as exc:
        pytest.fail(f"summary raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# audit_path
# ---------------------------------------------------------------------------

def test_audit_path_default(monkeypatch):
    monkeypatch.delenv("TONY_DECISION_AUDIT_FILE", raising=False)
    p = da.audit_path()
    assert p.name == "decision-audit.jsonl"
    assert "workspace" in str(p)


def test_audit_path_env_override(monkeypatch, tmp_path):
    custom = str(tmp_path / "custom.jsonl")
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", custom)
    assert str(da.audit_path()) == custom


def test_audit_path_read_at_call_time(monkeypatch, tmp_path):
    # Changing the env between two calls must produce different paths
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", str(tmp_path / "first.jsonl"))
    p1 = da.audit_path()
    monkeypatch.setenv("TONY_DECISION_AUDIT_FILE", str(tmp_path / "second.jsonl"))
    p2 = da.audit_path()
    assert p1 != p2
    assert p1.name == "first.jsonl"
    assert p2.name == "second.jsonl"
