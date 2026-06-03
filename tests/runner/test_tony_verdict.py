from runner.tools import tony_verdict as tv


def test_override_requires_target_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    r = tv.write_tony_verdict(symbol="X", tony_score=40, verdict="override", thesis="t")
    assert "error" in r and "target" in r["error"].lower()


def test_adjust_with_levels_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    r = tv.write_tony_verdict(symbol="X", tony_score=70, verdict="adjust", thesis="t",
                              target=30.0, stop=25.0)
    assert r.get("success")


def test_reaffirm_allows_blank_levels(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    assert tv.write_tony_verdict(symbol="X", tony_score=80, verdict="reaffirm", thesis="t").get("success")


def test_bad_verdict_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    assert "error" in tv.write_tony_verdict(symbol="X", tony_score=80, verdict="buy", thesis="t")


def test_same_day_symbol_replaces(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    tv.write_tony_verdict(symbol="X", tony_score=50, verdict="pass", thesis="a")
    r = tv.write_tony_verdict(symbol="X", tony_score=90, verdict="reaffirm", thesis="b")
    assert r["total_verdicts"] == 1  # replaced, not stacked
