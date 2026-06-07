"""experience_memory tests (T1.2/T1.7): quarantine→promote→retire lifecycle, confidence decay,
shadow-gate ingest, and FinMem-style retrieval. Hermetic — pure dicts + tmp_path persistence."""
import pytest

from runner.ledger import experience_memory as em


def _pick(tags, ret, resolved="2026-05-10", symbol="AAA"):
    return {"symbol": symbol, "evidence": list(tags), "return_pct": ret,
            "resolved_date": resolved, "right": ret > 0}


def test_new_rule_starts_quarantined_at_half_confidence():
    r = em.new_rule("tag X wins", ["x"], created="2026-05-01")
    assert r["state"] == "quarantine"
    assert em.confidence(r, as_of="2026-05-01") == pytest.approx(0.5)


def test_confidence_rises_with_help_falls_with_contradiction():
    r = em.new_rule("x", ["x"], created="2026-05-01")
    for _ in range(8):
        em.observe(r, True, on_date="2026-05-02")
    assert em.confidence(r, as_of="2026-05-02") > 0.7
    for _ in range(8):
        em.observe(r, False, on_date="2026-05-02")
    assert em.confidence(r, as_of="2026-05-02") == pytest.approx(0.5, abs=0.05)


def test_confidence_decays_toward_prior_when_stale():
    r = em.new_rule("x", ["x"], created="2026-01-01")
    for _ in range(10):
        em.observe(r, True, on_date="2026-01-01")
    fresh = em.confidence(r, as_of="2026-01-02")
    stale = em.confidence(r, as_of="2026-06-01")  # 5 months later, no new support
    assert stale < fresh and stale == pytest.approx(0.5, abs=0.12)


def test_promote_only_with_enough_obs_and_confidence():
    r = em.new_rule("x", ["x"], created="2026-05-01")
    em.observe(r, True, on_date="2026-05-02")
    em.observe(r, True, on_date="2026-05-02")
    em.update_state(r, as_of="2026-05-02")
    assert r["state"] == "quarantine"  # only 2 obs < min_obs -> not promoted (fail-closed)
    for _ in range(6):
        em.observe(r, True, on_date="2026-05-03")
    em.update_state(r, as_of="2026-05-03")
    assert r["state"] == "active"


def test_active_rule_retires_when_contradicted():
    r = em.new_rule("x", ["x"], created="2026-05-01")
    for _ in range(8):
        em.observe(r, True, on_date="2026-05-02")
    em.update_state(r, as_of="2026-05-02")
    assert r["state"] == "active"
    for _ in range(20):
        em.observe(r, False, on_date="2026-05-03")
    em.update_state(r, as_of="2026-05-03")
    assert r["state"] == "retired"


def test_stale_rule_retires_anti_forgetting():
    r = em.new_rule("x", ["x"], created="2026-01-01")
    for _ in range(8):
        em.observe(r, True, on_date="2026-01-01")
    em.update_state(r, as_of="2026-01-01")
    assert r["state"] == "active"
    em.update_state(r, as_of="2026-06-01")  # idle > max_idle_days
    assert r["state"] == "retired"


def test_score_edge_rule_win_and_avoid_directions():
    picks = [_pick(["x"], 5.0), _pick(["x"], -5.0), _pick(["x"], 3.0), _pick(["y"], -9.0)]
    win = em.score_edge_rule(em.new_rule("x wins", ["x"], direction="win"), picks)
    assert win == {"helped": 2, "hurt": 1, "n": 3}  # the 'y' pick is not a test
    avoid = em.score_edge_rule(em.new_rule("x loses", ["x"], direction="avoid"), picks)
    assert avoid == {"helped": 1, "hurt": 2, "n": 3}


def test_ingest_is_the_shadow_gate():
    # a quarantined rule accumulates evidence from resolved picks and promotes only after proving out
    rule = em.new_rule("good_setup wins", ["good_setup"], direction="win", created="2026-05-01")
    picks = [_pick(["good_setup"], 5.0, symbol=f"S{i}") for i in range(6)]
    em.ingest([rule], picks, as_of="2026-05-10")
    assert rule["state"] == "active" and rule["helped"] == 6


def test_relevant_rules_retrieves_active_by_relevance():
    a = em.new_rule("energy avoid", ["energy"], regime="risk_off", created="2026-05-01")
    b = em.new_rule("tech win", ["tech"], created="2026-05-01")
    c = em.new_rule("quarantined", ["energy"], created="2026-05-01")
    for r in (a, b):
        for _ in range(8):
            em.observe(r, True, on_date="2026-05-05")
        em.update_state(r, as_of="2026-05-05")
    assert a["state"] == "active" and c["state"] == "quarantine"
    out = em.relevant_rules([a, b, c], tags=["energy"], regime="risk_off", k=5, as_of="2026-05-06")
    assert a in out and c not in out  # quarantined never retrieved
    assert out[0] is a  # best tag+regime match ranks first


def test_persistence_roundtrip(tmp_path):
    rules = [em.new_rule("x", ["x"]), em.new_rule("y", ["y"])]
    p = tmp_path / "rules.json"
    assert em.save_rules(rules, p) is True
    assert len(em.load_rules(p)) == 2
    assert em.load_rules(tmp_path / "missing.json") == []  # fail-soft
