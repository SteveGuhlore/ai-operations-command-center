# tests/runner/test_outreach_synthesis.py
import importlib
from pathlib import Path


def _fresh(tmp_path, monkeypatch):
    import scripts.outreach_synthesis as syn
    importlib.reload(syn)
    monkeypatch.setattr(syn, "CRM_FILE", tmp_path / "crm.md")
    monkeypatch.setattr(syn, "LEARNINGS_DIR", tmp_path / "learnings")
    monkeypatch.setattr(syn, "PROMPT_FILE", tmp_path / "outreach_worker.md")
    return syn


_HEADER = (
    "# Outreach CRM\n\n"
    "| Business | Type | City | Contact | Channel | Status | Date | Notes |\n"
    "|---|---|---|---|---|---|---|---|\n"
)

_PROMPT = (
    "# Pitch\n\nMission line.\n\n"
    "<!-- AUTO-CALIBRATION:START -->\n_No calibration learned yet._\n<!-- AUTO-CALIBRATION:END -->\n\n"
    "## Offer\nbody\n"
)


def _row(name, typ, city, channel, status):
    return f"| {name} | {typ} | {city} | c@x | {channel} | {status} | 2026-05-28 | n |\n"


def test_rows_parsed(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.CRM_FILE.write_text(_HEADER + _row("A", "salon", "Boston, MA", "email", "email_sent"), encoding="utf-8")
    rows = syn._rows()
    assert len(rows) == 1 and rows[0]["status"] == "email_sent" and rows[0]["channel"] == "email"


def test_missing_crm_yields_nothing(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    assert syn._rows() == []
    assert syn.find_call_queued_overreliance([]) == {"triggered": False, "total": 0, "call_queued": 0, "rate": 0.0}


def test_call_queued_overreliance_triggers(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    rows = [{"status": "call_queued", "channel": "phone", "type": "t", "city": "c"} for _ in range(8)]
    rows += [{"status": "email_sent", "channel": "email", "type": "t", "city": "c"} for _ in range(4)]
    over = syn.find_call_queued_overreliance(rows, min_rows=10, frac=0.5)
    assert over["triggered"] and over["call_queued"] == 8 and over["total"] == 12


def test_call_queued_not_triggered_when_healthy(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    rows = [{"status": "call_queued", "channel": "phone", "type": "t", "city": "c"} for _ in range(3)]
    rows += [{"status": "dm_queued", "channel": "instagram", "type": "t", "city": "c"} for _ in range(9)]
    assert syn.find_call_queued_overreliance(rows, min_rows=10, frac=0.5)["triggered"] is False


def test_channel_mix_normalizes(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    rows = [{"channel": "Instagram"}, {"channel": "ig"}, {"channel": "Email"}, {"channel": "phone/call"}]
    mix = syn.channel_mix(rows)
    assert mix.get("instagram") == 2 and mix.get("email") == 1 and mix.get("phone") == 1


def test_segment_winners_only_positive(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    rows = [
        {"status": "replied", "type": "salon", "city": "Boston, MA"},
        {"status": "closed", "type": "cafe", "city": "Lowell, MA"},
        {"status": "call_queued", "type": "gym", "city": "Lynn, MA"},
    ]
    winners = syn.find_segment_winners(rows)
    assert "salon in Boston, MA" in winners and "cafe in Lowell, MA" in winners
    assert all("gym" not in w for w in winners)


def test_build_calibration_empty_when_no_signal(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    text = syn.build_calibration({"triggered": False, "total": 5, "call_queued": 1, "rate": 0.2}, {}, [], 0.0)
    assert "No calibration learned yet" in text


def test_build_calibration_includes_directives(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    text = syn.build_calibration(
        {"triggered": True, "total": 20, "call_queued": 15, "rate": 0.75},
        {"instagram": 20}, ["salon in Boston, MA"], 299.0)
    assert "call_queued" in text and "salon in Boston, MA" in text and "299" in text


def test_update_calibration_block_only_touches_block(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.PROMPT_FILE.write_text(_PROMPT, encoding="utf-8")
    assert syn.update_calibration_block("**Directive.**") is True
    out = syn.PROMPT_FILE.read_text(encoding="utf-8")
    assert "**Directive.**" in out
    assert out.startswith("# Pitch")          # persona above the block untouched
    assert "## Offer\nbody" in out            # content below the block untouched


def test_update_calibration_block_missing_markers_returns_false(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.PROMPT_FILE.write_text("# Pitch\n\nNo markers here.\n", encoding="utf-8")
    assert syn.update_calibration_block("x") is False


def test_daily_hook_invokes_outreach_synthesis():
    import inspect
    import runner.main as m
    src = inspect.getsource(m._maybe_run_learning)
    assert "outreach_synthesis.py" in src
    assert (Path(m.__file__).parent.parent / "scripts" / "outreach_synthesis.py").exists()
