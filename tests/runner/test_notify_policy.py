"""notify_policy — keep reprice alerts instant but quiet (dedup + materiality + cooldown),
escalate the breakeven lock, and fail OPEN so a policy bug never silences a real alert."""

from runner.tools import notify_policy as np


def _wire(tmp_path, monkeypatch, cooldown="90", minmove="0.75"):
    monkeypatch.setattr(np, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setenv("TONY_REPRICE_COOLDOWN_MIN", cooldown)
    monkeypatch.setenv("TONY_REPRICE_MIN_MOVE_PCT", minmove)


def test_first_reprice_for_symbol_sends(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    d = np.gate_reprice("AAA", stop=10.0, target=12.0, now=1000)
    assert d["send"] and not d["lock"] and d["reason"] == "material_move"


def test_exact_duplicate_is_dropped(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch)
    np.gate_reprice("AAA", 10.0, 12.0, now=1000)
    d = np.gate_reprice("AAA", 10.0, 12.0, now=10_000)  # identical, even long after
    assert not d["send"] and d["reason"] == "duplicate"


def test_immaterial_move_is_dropped(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch, minmove="1.0")
    np.gate_reprice("AAA", 10.0, 12.0, now=1000)
    d = np.gate_reprice("AAA", 10.05, 12.0, now=10_000)  # +0.5% < 1% threshold
    assert not d["send"] and d["reason"] == "immaterial"


def test_material_move_within_cooldown_is_dropped(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch, cooldown="90", minmove="0.5")
    np.gate_reprice("AAA", 10.0, 12.0, now=1000)
    d = np.gate_reprice("AAA", 10.2, 12.0, now=1000 + 600)  # +2% but only 10 min later
    assert not d["send"] and d["reason"] == "cooldown"


def test_material_move_after_cooldown_sends(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch, cooldown="90", minmove="0.5")
    np.gate_reprice("AAA", 10.0, 12.0, now=1000)
    d = np.gate_reprice("AAA", 10.2, 12.0, now=1000 + 91 * 60)
    assert d["send"] and d["reason"] == "material_move"


def test_suppressed_micro_moves_accumulate_vs_last_sent(tmp_path, monkeypatch):
    # Anchor is the last NOTIFIED stop, so a string of tiny moves eventually clears the threshold.
    _wire(tmp_path, monkeypatch, cooldown="0", minmove="1.0")
    np.gate_reprice("AAA", 10.0, 12.0, now=0)  # sent, anchor=10.0
    assert not np.gate_reprice("AAA", 10.05, 12.0, now=1)[
        "send"
    ]  # +0.5% drop, anchor stays 10.0
    assert np.gate_reprice("AAA", 10.2, 12.0, now=2)["send"]  # +2% vs 10.0 -> sends


def test_breakeven_lock_escalates_even_within_cooldown(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch, cooldown="90", minmove="0.5")
    np.gate_reprice(
        "AAA", 9.0, 12.0, entry=10.0, now=1000
    )  # stop below entry, first send
    d = np.gate_reprice(
        "AAA", 10.5, 12.0, entry=10.0, now=1000 + 60
    )  # crosses entry, in cooldown
    assert d["send"] and d["lock"] and d["reason"] == "breakeven_lock"


def test_breakeven_lock_fires_only_once(tmp_path, monkeypatch):
    _wire(tmp_path, monkeypatch, cooldown="0", minmove="0")
    first = np.gate_reprice("AAA", 10.5, 12.0, entry=10.0, now=1000)
    assert first["lock"]
    second = np.gate_reprice("AAA", 11.0, 12.0, entry=10.0, now=2000)
    assert not second["lock"]  # already locked -> normal path, not a second lock note


def test_fail_safe_on_unreadable_state(tmp_path, monkeypatch):
    # A bad state path must never SILENCE an alert: I/O errors are swallowed and the gate still
    # sends (here via the normal first-move path, since a failed load looks like "no prior state").
    bad = tmp_path / "is_a_dir"
    bad.mkdir()
    monkeypatch.setattr(np, "STATE_FILE", bad)
    assert np.gate_reprice("AAA", 10.0, 12.0, now=1000)["send"]


def test_notify_reprice_routes_through_gate(tmp_path, monkeypatch):
    from runner.tools import notify

    monkeypatch.setattr(np, "STATE_FILE", tmp_path / "s.json")
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TONY_NOTIFY_POLICY", "on")
    monkeypatch.setenv("TONY_REPRICE_COOLDOWN_MIN", "90")
    monkeypatch.setenv("TONY_REPRICE_MIN_MOVE_PCT", "0.5")
    sent: list = []
    monkeypatch.setattr(
        notify, "notify", lambda *a, **k: (sent.append(1), {"sent": True})[1]
    )
    notify.notify_reprice("AAA", 10, 12.0, 10.0)  # first -> sends
    r = notify.notify_reprice("AAA", 10, 12.0, 10.0)  # identical -> suppressed, no send
    assert len(sent) == 1
    assert r["sent"] is False and r["reason"] == "duplicate"


def test_notify_reprice_kill_switch_restores_legacy(tmp_path, monkeypatch):
    from runner.tools import notify

    monkeypatch.setattr(np, "STATE_FILE", tmp_path / "s.json")
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TONY_NOTIFY_POLICY", "off")  # kill-switch: every move sends
    sent: list = []
    monkeypatch.setattr(
        notify, "notify", lambda *a, **k: (sent.append(1), {"sent": True})[1]
    )
    notify.notify_reprice("AAA", 10, 12.0, 10.0)
    notify.notify_reprice(
        "AAA", 10, 12.0, 10.0
    )  # identical still sends with policy off
    assert len(sent) == 2
