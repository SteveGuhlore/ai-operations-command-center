"""Deep-dive cooldown ledger — a name can be re-graded after the window, but not 'over and over'."""
import importlib


def _fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_DEEPDIVE_LEDGER_FILE", str(tmp_path / "dd.json"))
    from runner.ledger import deepdive_ledger as dl
    importlib.reload(dl)
    return dl


def test_due_until_marked_then_on_cooldown(tmp_path, monkeypatch):
    dl = _fresh(tmp_path, monkeypatch)
    assert dl.due_for_deepdive("AAA") is True          # never dived
    dl.mark_deepdived("aaa")                            # case-insensitive
    assert dl.due_for_deepdive("AAA", cooldown_hours=4) is False   # within cooldown
    assert dl.due_for_deepdive("BBB") is True           # a different name is still due


def test_cooldown_elapses(tmp_path, monkeypatch):
    dl = _fresh(tmp_path, monkeypatch)
    dl.mark_deepdived("AAA")
    assert dl.due_for_deepdive("AAA", cooldown_hours=0) is True    # 0h window -> immediately due again


def test_blank_symbol_not_due(tmp_path, monkeypatch):
    dl = _fresh(tmp_path, monkeypatch)
    assert dl.due_for_deepdive("") is False
    assert dl.due_for_deepdive(None) is False
