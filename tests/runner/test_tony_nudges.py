from runner.tools import tony_nudges as nudges


def test_equity_high_fires_once_per_high(tmp_path, monkeypatch):
    monkeypatch.setattr(nudges, "STATE_FILE", tmp_path / "nudge-state.json")
    posts = []
    monkeypatch.setattr(nudges, "broadcast", lambda text, **k: posts.append(text) or {"sent": True})
    monkeypatch.setattr(nudges, "notify", lambda text, **k: {"sent": True})
    # first observation records the mark (from the isolated state file), does not shout
    monkeypatch.setattr(nudges, "_tony_equity", lambda: 1_010_000.0)
    assert nudges.maybe_equity_high()["sent"] is False
    # a higher equity than the stored peak -> fires
    monkeypatch.setattr(nudges, "_tony_equity", lambda: 1_020_000.0)
    assert nudges.maybe_equity_high()["sent"] is True
    assert "high" in posts[-1].lower()
    # same equity -> de-duped, no new post
    assert nudges.maybe_equity_high()["sent"] is False


def test_eod_signoff_once_per_day(tmp_path, monkeypatch):
    monkeypatch.setattr(nudges, "STATE_FILE", tmp_path / "nudge-state.json")
    posts = []
    monkeypatch.setattr(nudges, "broadcast", lambda text, **k: posts.append(text) or {"sent": True})
    monkeypatch.setattr(nudges, "notify", lambda text, **k: {"sent": True})
    monkeypatch.setattr(nudges, "_daily_wrap_text", lambda: "Good day — up $1,200.")
    assert nudges.maybe_eod_signoff("2026-06-08")["sent"] is True
    assert nudges.maybe_eod_signoff("2026-06-08")["sent"] is False   # already signed off today
