import scripts.opportunity_synthesis as syn


def _dd(slug, composite, status="deepdived"):
    return {"slug": slug, "composite": composite, "phase": "deepdived",
            "poc": "—", "status": status, "pod": "—"}


def test_over_penalization_triggers_when_mostly_low():
    rows = [_dd("a", "55", "rejected"), _dd("b", "57"), _dd("c", "60"),
            _dd("d", "80", "promoted")]  # 3 of 4 deepdived below 75 → 0.75
    sig = syn.find_over_penalization(rows)
    assert sig["triggered"] is True
    assert sig["deepdived"] == 4


def test_over_penalization_not_triggered_when_healthy():
    rows = [_dd("a", "80", "promoted"), _dd("b", "78"), _dd("c", "55", "rejected"),
            {"slug": "d", "composite": "30", "phase": "scouted", "poc": "—",
             "status": "scouted", "pod": "—"}]  # only 1 of 3 deepdived low
    sig = syn.find_over_penalization(rows)
    assert sig["triggered"] is False


def test_build_calibration_anti_saturation_when_triggered():
    txt = syn.build_calibration({"triggered": True, "deepdived": 4, "low": 3, "rate": 0.75}, winners=[])
    assert "wedge" in txt.lower()
    assert "saturat" in txt.lower()


def test_build_calibration_reinforces_winners():
    txt = syn.build_calibration({"triggered": False, "deepdived": 1, "low": 0, "rate": 0.0},
                                winners=[{"slug": "ai-x", "revenue": 120.0}])
    assert "ai-x" in txt
    assert "real" in txt.lower()


def test_build_calibration_baseline_when_nothing():
    txt = syn.build_calibration({"triggered": False, "deepdived": 0, "low": 0, "rate": 0.0}, winners=[])
    assert "No calibration" in txt


def test_build_calibration_includes_deaths_when_died():
    txt = syn.build_calibration({"triggered": False, "deepdived": 0, "low": 0, "rate": 0.0},
                                winners=[], deaths=2)
    assert "died 2" in txt
    assert "survival is not guaranteed" in txt.lower()


def test_update_calibration_block_replaces_only_region(tmp_path, monkeypatch):
    f = tmp_path / "p.md"
    f.write_text(
        "# Top\nbefore-text\n"
        "<!-- AUTO-CALIBRATION:START -->\nOLD CONTENT\n<!-- AUTO-CALIBRATION:END -->\n"
        "after-text\n", encoding="utf-8")
    monkeypatch.setattr(syn, "PROMPT_FILE", f)
    assert syn.update_calibration_block("NEW DIRECTIVE") is True
    txt = f.read_text(encoding="utf-8")
    assert "NEW DIRECTIVE" in txt
    assert "OLD CONTENT" not in txt
    assert "before-text" in txt and "after-text" in txt
    assert "AUTO-CALIBRATION:START" in txt and "AUTO-CALIBRATION:END" in txt


def test_update_calibration_block_noop_without_markers(tmp_path, monkeypatch):
    f = tmp_path / "p.md"
    f.write_text("# No markers here\n", encoding="utf-8")
    monkeypatch.setattr(syn, "PROMPT_FILE", f)
    assert syn.update_calibration_block("X") is False
