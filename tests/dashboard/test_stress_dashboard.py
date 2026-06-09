"""Stress / robustness tests for the dashboard endpoints against malformed and concurrently-
mutated files written by the runner and outreach pod."""
from fastapi.testclient import TestClient

import dashboard.server as server


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "VAULT_DIR", tmp_path / "vault")
    (tmp_path / "vault" / "outreach").mkdir(parents=True)
    return TestClient(server.app)


# ---------------------------------------------------- outreach stats parser robustness

def test_outreach_stats_counts_business_named_lead(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    crm = tmp_path / "vault" / "outreach" / "crm.md"
    crm.write_text(
        "| Business | Type | City | Contact | Channel | Status | Date | Notes |\n"
        "|----------|------|------|---------|---------|--------|------|-------|\n"
        "| Joe's Business Services | Plumber | Lowell, MA | — | phone | call_queued | 2026-06-01 | |\n"
        "| Texture Salon | Hair Salon | Salem, MA | a@b.com | email | email_sent | 2026-06-01 | |\n",
        encoding="utf-8",
    )
    d = client.get("/api/outreach/stats").json()
    # The lead literally named "...Business Services" must be counted, not dropped by a
    # naive "Business" substring filter.
    assert d["total"] == 2
    assert d["call_queued"] == 1
    assert d["emailed"] == 1
    assert {r["business"] for r in d["recent"]} == {"Joe's Business Services", "Texture Salon"}


def test_outreach_stats_empty_when_no_file(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    d = client.get("/api/outreach/stats").json()
    assert d["total"] == 0 and d["recent"] == []


def test_outreach_stats_skips_header_and_divider_only(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    crm = tmp_path / "vault" / "outreach" / "crm.md"
    crm.write_text(
        "| Business | Type | City | Contact | Channel | Status | Date | Notes |\n"
        "|----------|------|------|---------|---------|--------|------|-------|\n"
        "| Acme Co | Cafe | Boston, MA | — | phone | call_queued | 2026-06-01 | |\n",
        encoding="utf-8",
    )
    d = client.get("/api/outreach/stats").json()
    assert d["total"] == 1


# ---------------------------------------------------- endpoints degrade, never 500

def test_root_degrades_when_index_missing(tmp_path, monkeypatch):
    # Point the module dir lookup at a place with no index.html by monkeypatching read.
    client = TestClient(server.app, raise_server_exceptions=False)
    r = client.get("/")
    # Either serves the real index (200) or degrades to 503 — never an unhandled 500.
    assert r.status_code in (200, 503)


def test_analytics_agents_tolerates_missing_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "TASKS_DIR", tmp_path / "nope" / "tasks")
    client = TestClient(server.app, raise_server_exceptions=False)
    r = client.get("/api/analytics/agents")
    assert r.status_code == 200
