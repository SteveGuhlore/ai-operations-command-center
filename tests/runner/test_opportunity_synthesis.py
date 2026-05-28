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


def test_tune_prompt_skips_without_api_key(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
    syn.PROMPT_FILE.write_text("## Scout workflow\noriginal\n", encoding="utf-8")

    def _boom(*a, **k):  # OpenAI must never be constructed without a key
        raise AssertionError("OpenAI client constructed without API key")

    monkeypatch.setattr(syn, "OpenAI", _boom)
    syn._tune_prompt([{"slug": "a", "composite": "82", "poc": "dead"}])
    assert syn.PROMPT_FILE.read_text(encoding="utf-8") == "## Scout workflow\noriginal\n"


def test_tune_prompt_skips_when_no_divergence(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "x")

    def _boom(*a, **k):
        raise AssertionError("OpenAI client constructed when nothing diverged")

    monkeypatch.setattr(syn, "OpenAI", _boom)
    syn._tune_prompt([])  # must early-return before touching the client


def test_tune_prompt_rewrites_when_guard_satisfied(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "x")
    syn.PROMPT_FILE.write_text("## Scout workflow\noriginal\n", encoding="utf-8")
    revised = "## Scout workflow\nrevised — avoid over-scoring dead PoCs\n"

    class _Msg:
        content = revised

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _FakeClient:
        def __init__(self, *a, **k):
            self.chat = self

        @property
        def completions(self):
            return self

        def create(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(syn, "OpenAI", _FakeClient)
    syn._tune_prompt([{"slug": "a", "composite": "82", "poc": "dead"}])
    assert syn.PROMPT_FILE.read_text(encoding="utf-8") == revised


def test_tune_prompt_rejects_output_missing_guard_section(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "x")
    original = "## Scout workflow\noriginal\n"
    syn.PROMPT_FILE.write_text(original, encoding="utf-8")

    class _Msg:
        content = "garbage output that dropped every section"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _FakeClient:
        def __init__(self, *a, **k):
            self.chat = self

        @property
        def completions(self):
            return self

        def create(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(syn, "OpenAI", _FakeClient)
    syn._tune_prompt([{"slug": "a", "composite": "82", "poc": "dead"}])
    assert syn.PROMPT_FILE.read_text(encoding="utf-8") == original


def test_daily_hook_invokes_synthesis_script():
    """The nightly learning hook in runner.main must shell out to the synthesis script."""
    import inspect
    import runner.main as m

    src = inspect.getsource(m._maybe_run_learning)
    assert "opportunity_synthesis.py" in src

    assert (Path(m.__file__).parent.parent / "scripts" / "opportunity_synthesis.py").exists()
