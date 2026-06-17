"""Regression tests for the 2026-06-17 multi-review auto-fix batch (Bucket 1).

Each test pins a specific Codex-flagged finding so the containment / robustness
guard can't silently regress. Architectural findings (dashboard auth, alpaca_paper
interprocess lock, prompts.py injection) are tracked separately in the run's PLAN.md.
"""
import pytest

from runner.tools import files, landing, opportunity, vault_memory
from runner.eval import data_contract
from runner.agents.tool_runner import dispatch_tool


# --- files._safe_path: sibling-prefix traversal (#14) ---------------------------

def test_safe_path_accepts_in_repo():
    assert files._safe_path("workspace/x.txt") is not None


def test_safe_path_rejects_parent_escape():
    assert files._safe_path("../../etc/passwd") is None


def test_safe_path_rejects_sibling_prefix(monkeypatch, tmp_path):
    root = tmp_path / "AI Operations Command Center"
    root.mkdir()
    monkeypatch.setattr(files, "PROJECT_ROOT", root)
    # A sibling dir that shares the resolved-string prefix — the old startswith
    # check let this through; is_relative_to rejects it.
    assert files._safe_path("../AI Operations Command Center-backup/secret") is None


# --- vault_memory: role_id traversal (#15) -------------------------------------

def test_write_memory_rejects_traversal_role(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_memory, "AGENTS_MEMORY_DIR", tmp_path)
    res = vault_memory.write_memory("../evil", "pattern", "x")
    assert "error" in res
    # Nothing was written outside the vault dir.
    assert not (tmp_path.parent / "evil").exists()


def test_write_memory_accepts_valid_role(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_memory, "AGENTS_MEMORY_DIR", tmp_path)
    res = vault_memory.write_memory("market_research_worker", "pattern", "learned x")
    assert res.get("saved") is True
    assert (tmp_path / "market_research_worker" / "memory.md").exists()


def test_load_agent_memory_rejects_bad_role(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_memory, "AGENTS_MEMORY_DIR", tmp_path)
    assert vault_memory.load_agent_memory("../../etc") == ""


# --- landing slug traversal (#11) ----------------------------------------------

def test_landing_path_rejects_traversal():
    with pytest.raises(ValueError):
        landing._path("../logs/x")


def test_landing_reads_are_defensive_on_bad_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)
    assert landing.landing_exists("../x") is False
    assert landing.read_landing_state("../x") == {}


def test_landing_valid_slug_still_works(tmp_path, monkeypatch):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)
    landing.write_landing_state("ai-x", status="draft")
    assert landing.read_landing_state("ai-x")["status"] == "draft"


# --- opportunity slug traversal (#13, #16) -------------------------------------

def test_log_opportunity_rejects_bad_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity, "OPP_DIR", tmp_path)
    monkeypatch.setattr(opportunity, "LEDGER_FILE", tmp_path / "ledger.md")
    res = opportunity.log_opportunity(
        "../../poison", "one", "p", "who", 1, 1, 1, 1, 1, 1)
    assert "error" in res
    assert not (tmp_path.parent / "poison.md").exists()


def test_grade_poc_rejects_bad_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity, "OPP_DIR", tmp_path)
    monkeypatch.setattr(opportunity, "LEDGER_FILE", tmp_path / "ledger.md")
    res = opportunity.grade_poc("../evil", "promising", "because")
    assert "error" in res


# --- data_contract.graded_picks: malformed numeric must not crash (#8) ---------

def test_graded_picks_skips_bad_return_pct(monkeypatch):
    monkeypatch.setattr(data_contract.sc, "_matched_verdict",
                        lambda o, v: {"verdict": "buy", "confidence": "high"})
    monkeypatch.setattr(data_contract.sc, "_is_right", lambda verdict, ret: True)
    outcomes = [
        {"symbol": "BAD", "resolved_date": "2026-06-10", "return_pct": "not-a-number"},
        {"symbol": "OK", "resolved_date": "2026-06-11", "return_pct": "1.5"},
    ]
    graded = data_contract.graded_picks(outcomes=outcomes, verdicts=[{}])
    # The malformed row is skipped, the good one survives — no crash.
    assert [g["symbol"] for g in graded] == ["OK"]


# --- base.py unknown-tool: dispatch_tool contract the catch relies on (#9) ------

def test_dispatch_tool_raises_on_unknown():
    with pytest.raises(ValueError):
        dispatch_tool("definitely_not_a_real_tool", {})
