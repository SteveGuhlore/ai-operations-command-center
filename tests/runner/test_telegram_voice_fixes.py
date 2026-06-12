"""Telegram pipeline fixes: sentence-aware thesis trim + wikilink stripping, the deterministic
end-of-day closed-trades ledger, and ET-day consistency in the realized 'today' aggregates."""
import json

from runner.ledger import alpaca_paper as ap
from runner.tools import tony_voice as tv
from runner.tools import tony_nudges as tn


def _verdict(thesis):
    return [{"symbol": "GE", "date": "2026-06-12", "thesis": thesis}]


def test_thesis_strips_wikilinks_and_never_cuts_midword():
    long = ("[[GE]] shows a [[Breakout Watch]] setup near its 52-week high. "
            + "Another full sentence of analysis follows here for length. " * 14)
    out = ap._verdict_thesis(_verdict(long), "GE")
    assert "[[" not in out and "]]" not in out          # raw Obsidian links never reach Telegram
    assert len(out) <= ap._THESIS_MAX + 1
    assert out.endswith(".") or out.endswith("…")        # sentence or whole-word boundary
    if out.endswith("…"):
        assert " " in out and not out[:-1].endswith(" ")  # word-boundary cut, not mid-word


def test_thesis_short_passes_untouched():
    assert ap._verdict_thesis(_verdict("Clean short thesis."), "GE") == "Clean short thesis."


def test_day_ledger_lists_every_exit_and_net():
    rows = [{"symbol": "LRCX", "realized_pl": 958.0, "pct": 6.4, "date": "2026-06-12", "reason": "close"},
            {"symbol": "DAL", "realized_pl": 367.0, "pct": 4.1, "date": "2026-06-12", "reason": "close"},
            {"symbol": "BEN", "realized_pl": -118.0, "pct": -1.2, "date": "2026-06-12", "reason": "close"}]
    out = tv.say_day_ledger(rows, {"count": 3, "wins": 2, "losses": 1, "realized_pl": 1207.0})
    for sym in ("LRCX", "DAL", "BEN"):
        assert sym in out                                # EVERY exit appears — nothing omitted
    assert "+$1,207" in out and "2 win / 1 loss" in out
    assert tv.say_day_ledger([], {}) == ""               # quiet day -> no section


def test_eod_signoff_carries_the_ledger(tmp_path, monkeypatch):
    import runner.ledger.tony_realized as tr
    monkeypatch.setattr(tr, "REALIZED_FILE", tmp_path / "realized.json")
    # write realized rows for the day directly
    rows = [{"symbol": "LRCX", "qty": 30, "entry": 328.0, "exit": 360.19, "realized_pl": 958.0,
             "pct": 6.4, "reason": "close", "date": "2026-06-12"}]
    (tmp_path / "realized.json").write_text(json.dumps(rows))
    monkeypatch.setattr(tn, "STATE_FILE", tmp_path / "nudge.json")
    monkeypatch.setattr(tn, "_daily_wrap_text", lambda: "My account is holding strong.")
    sent = {}
    monkeypatch.setattr(tn, "_send_both", lambda text: sent.update(text=text) or {"sent": True})
    tn.maybe_eod_signoff("2026-06-12")
    assert "LRCX" in sent["text"] and "+$958" in sent["text"]   # the sells are IN the wrap now
    assert "That's a wrap" in sent["text"]
    # and the once-per-day dedup still holds
    assert tn.maybe_eod_signoff("2026-06-12")["reason"] == "already"


def test_realized_today_uses_et_trading_day(tmp_path, monkeypatch):
    import runner.ledger.tony_realized as tr
    monkeypatch.setattr(tr, "REALIZED_FILE", tmp_path / "realized.json")
    monkeypatch.setattr(tr, "_trading_day", lambda: "2026-06-11")
    rows = [{"symbol": "WIN", "realized_pl": 500.0, "date": "2026-06-11", "reason": "target"}]
    (tmp_path / "realized.json").write_text(json.dumps(rows))
    s = tr.summary()
    # at 9 PM ET (UTC already 06-12) the day's exits must still count as TODAY
    assert s["today"]["count"] == 1 and s["today"]["realized_pl"] == 500.0
