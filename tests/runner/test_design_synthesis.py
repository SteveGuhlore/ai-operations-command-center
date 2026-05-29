import scripts.design_synthesis as ds


def _row(slug, archetype):
    return {"slug": slug, "archetype": archetype, "type": "x", "date": "2026-05-29",
            "palette": "", "fonts": "", "notes": ""}


def test_overused_archetype_triggers():
    rows = [_row(f"s{i}", "Neon Glass") for i in range(5)] + [_row("s5", "Brutalist Mono")]
    sig = ds.find_overused_archetype(rows, recent=6, threshold=0.5)
    assert sig["triggered"] is True
    assert sig["archetype"] == "Neon Glass"


def test_overused_not_triggered_when_varied():
    rows = [_row("a", "Neon Glass"), _row("b", "Brutalist Mono"),
            _row("c", "Warm Organic"), _row("d", "Bold Editorial")]
    assert ds.find_overused_archetype(rows, recent=8, threshold=0.5)["triggered"] is False


def test_build_calibration_rotate_when_overused():
    txt = ds.build_design_calibration(
        {"triggered": True, "archetype": "Neon Glass", "count": 5, "window": 6}, winners=[])
    assert "rotate" in txt.lower()
    assert "Neon Glass" in txt


def test_build_calibration_reinforces_winners():
    txt = ds.build_design_calibration(
        {"triggered": False, "archetype": None, "count": 0, "window": 0},
        winners=[{"slug": "ai-x", "archetype": "Warm Organic", "revenue": 99.0}])
    assert "ai-x" in txt
    assert "Warm Organic" in txt


def test_build_calibration_baseline():
    txt = ds.build_design_calibration({"triggered": False, "archetype": None, "count": 0, "window": 0}, [])
    assert "No design calibration" in txt


def test_update_calibration_block_replaces_only_region(tmp_path, monkeypatch):
    f = tmp_path / "builder.md"
    f.write_text("# Clay\nintro\n<!-- DESIGN-CALIBRATION:START -->\nOLD\n<!-- DESIGN-CALIBRATION:END -->\ntail\n",
                 encoding="utf-8")
    monkeypatch.setattr(ds, "PROMPT_FILE", f)
    assert ds.update_calibration_block("ROTATE NOW") is True
    txt = f.read_text(encoding="utf-8")
    assert "ROTATE NOW" in txt and "OLD" not in txt
    assert "intro" in txt and "tail" in txt


def test_parse_log_skips_header(tmp_path, monkeypatch):
    f = tmp_path / "design_log.md"
    f.write_text("| date | slug_or_business | type | archetype | palette | fonts | notes |\n"
                 "|------|------|------|------|------|------|------|\n"
                 "| 2026-05-29 | marias-tacos | restaurant | Warm Organic | cream | Inter | hero |\n",
                 encoding="utf-8")
    monkeypatch.setattr(ds, "DESIGN_LOG", f)
    rows = ds.parse_log()
    assert len(rows) == 1
    assert rows[0]["archetype"] == "Warm Organic"
