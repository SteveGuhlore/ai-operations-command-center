# tests/runner/test_opportunity_synthesis.py
import importlib
from pathlib import Path


def _fresh(tmp_path, monkeypatch):
    import scripts.opportunity_synthesis as syn
    importlib.reload(syn)
    monkeypatch.setattr(syn, "LEDGER_FILE", tmp_path / "ledger.md")
    monkeypatch.setattr(syn, "LEARNINGS_DIR", tmp_path / "learnings")
    monkeypatch.setattr(syn, "PROMPT_FILE", tmp_path / "opportunity_worker.md")
    return syn


_HEADER = (
    "# Opportunity Ledger\n\n"
    "| slug | composite | phase | poc | system_fit | est_rev_mo | status | pod | updated |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def test_divergence_detects_high_score_dead(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.LEDGER_FILE.write_text(
        _HEADER
        + "| a | 82 | graded | dead | 9 | 900 | graded | — | 2026-05-27 |\n"
        + "| b | 80 | graded | promising | 8 | 800 | graded | — | 2026-05-27 |\n",
        encoding="utf-8",
    )
    diverging = syn.find_divergence(threshold=75)
    assert any(rr["slug"] == "a" for rr in diverging)
    assert all(rr["slug"] != "b" for rr in diverging)


def test_writes_learnings_note(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.LEDGER_FILE.write_text(
        _HEADER + "| a | 82 | graded | dead | 9 | 900 | graded | — | 2026-05-27 |\n",
        encoding="utf-8",
    )
    syn.write_learnings(syn.find_divergence(75))
    notes = list((syn.LEARNINGS_DIR).glob("*-opportunities.md"))
    assert notes and "a" in notes[0].read_text(encoding="utf-8")


def test_weak_poc_diverges_dead_poc_diverges_promising_does_not(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.LEDGER_FILE.write_text(
        _HEADER
        + "| w | 90 | graded | weak | 9 | 900 | graded | — | 2026-05-27 |\n"
        + "| d | 76 | graded | dead | 8 | 800 | graded | — | 2026-05-27 |\n"
        + "| p | 99 | graded | promising | 9 | 999 | graded | — | 2026-05-27 |\n",
        encoding="utf-8",
    )
    slugs = {r["slug"] for r in syn.find_divergence(75)}
    assert slugs == {"w", "d"}


def test_below_threshold_not_diverging(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.LEDGER_FILE.write_text(
        _HEADER
        + "| low | 74 | graded | dead | 5 | 100 | graded | — | 2026-05-27 |\n"
        + "| on | 75 | graded | dead | 5 | 100 | graded | — | 2026-05-27 |\n",
        encoding="utf-8",
    )
    slugs = {r["slug"] for r in syn.find_divergence(75)}
    assert slugs == {"on"}


def test_missing_ledger_yields_no_divergence(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    assert syn.find_divergence(75) == []


def test_non_numeric_composite_skipped(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.LEDGER_FILE.write_text(
        _HEADER + "| bad | n/a | graded | dead | 9 | 900 | graded | — | 2026-05-27 |\n",
        encoding="utf-8",
    )
    assert syn.find_divergence(75) == []


def test_learnings_note_says_aligned_when_no_divergence(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    out = syn.write_learnings([])
    text = out.read_text(encoding="utf-8")
    assert "No divergence" in text


# NOTE: the old `_tune_prompt` full-file Gemini rewrite was removed (it could
# overwrite the whole persona). Self-learning now writes only the bounded
# AUTO-CALIBRATION block — see tests/runner/test_opportunity_synthesis_calibration.py.


def test_daily_hook_invokes_synthesis_script():
    """The nightly learning hook in runner.main must shell out to the synthesis script."""
    import inspect
    import runner.main as m

    src = inspect.getsource(m._maybe_run_learning)
    assert "opportunity_synthesis.py" in src

    assert (Path(m.__file__).parent.parent / "scripts" / "opportunity_synthesis.py").exists()
