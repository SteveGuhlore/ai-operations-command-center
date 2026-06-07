"""Append-only JSONL decision audit log for Tony Stocks.

Every trading decision — verdicts, orders, skips, breaker/risk events — is
written as one JSON line to a JSONL file. The append-only guarantee preserves
audit integrity; the file feeds the eval harness and post-mortems. All
functions are fail-soft so an audit failure can never break the trading cycle.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parent.parent.parent / "workspace" / "decision-audit.jsonl"


def audit_path() -> Path:
    """Return the active audit file path, reading TONY_DECISION_AUDIT_FILE env at call time."""
    return Path(os.environ.get("TONY_DECISION_AUDIT_FILE", str(_DEFAULT_PATH)))


def record_decision(kind: str, symbol: str | None = None, **fields) -> dict | None:
    """Append one event as a single JSON line to the audit file.

    Returns the written record dict on success, or None on any IO failure.
    Never raises into the caller.
    """
    now = datetime.now(timezone.utc)
    record = {
        "ts": now.isoformat(),
        "date": now.date().isoformat(),
        "kind": kind,
        "symbol": symbol,
        **fields,
    }
    try:
        path = audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception as exc:
        _log.warning("decision_audit record_decision failed: %s", exc)
        return None
    return record


def read_decisions(
    kind: str | None = None,
    since: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Read back audit records, optionally filtered by kind and/or since timestamp.

    kind   — exact match on the "kind" field.
    since  — ISO date or datetime string; records whose "ts" < since are excluded
              (lexicographic comparison works because ts is ISO-8601 UTC).
    limit  — return only the most recent N records (after filtering).

    Fail-soft: returns [] on any error. Malformed/non-JSON lines are skipped silently.
    """
    try:
        path = audit_path()
        try:
            text = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return []
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if kind is not None and rec.get("kind") != kind:
                continue
            if since is not None and rec.get("ts", "") < since:
                continue
            records.append(rec)
        if limit is not None:
            records = records[-limit:]
        return records
    except Exception as exc:
        _log.warning("decision_audit read_decisions failed: %s", exc)
        return []


def summary() -> dict:
    """Return {"total": int, "by_kind": {kind: count}, "by_date": {date: count}}.

    Fail-soft: returns zeroed structure on any error.
    """
    empty = {"total": 0, "by_kind": {}, "by_date": {}}
    try:
        records = read_decisions()
        by_kind: dict[str, int] = {}
        by_date: dict[str, int] = {}
        for rec in records:
            k = rec.get("kind", "")
            by_kind[k] = by_kind.get(k, 0) + 1
            d = rec.get("date", "")
            by_date[d] = by_date.get(d, 0) + 1
        return {"total": len(records), "by_kind": by_kind, "by_date": by_date}
    except Exception as exc:
        _log.warning("decision_audit summary failed: %s", exc)
        return empty
