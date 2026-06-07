import runner.ledger.alpaca_paper as ap


def test_verdict_levels_latest_valid_per_symbol():
    verdicts = [
        {"symbol": "SLB", "date": "2026-06-01", "target": 60.0, "stop": 54.0},
        {"symbol": "SLB", "date": "2026-06-03", "target": 62.0, "stop": 55.0},  # latest valid
        {"symbol": "SLB", "date": "2026-06-02", "target": 61.0, "stop": 55.0},
        {"symbol": "BAD", "date": "2026-06-03", "target": 10.0, "stop": 12.0},  # target<=stop -> ignore
        {"symbol": "NOL", "date": "2026-06-03"},                                # no levels -> ignore
    ]
    lv = ap._verdict_levels(verdicts)
    assert lv["SLB"] == {"target": 62.0, "stop": 55.0}
    assert "BAD" not in lv and "NOL" not in lv


def test_merge_levels_later_source_wins():
    verdict = {"SLB": {"target": 62.0, "stop": 55.0}, "X": {"target": 1.0, "stop": 0.5}}
    scanner = {"SLB": {"target": 63.0, "stop": 56.0}}
    merged = ap._merge_levels(verdict, scanner)
    assert merged["SLB"] == {"target": 63.0, "stop": 56.0}  # scanner (last) wins
    assert merged["X"] == {"target": 1.0, "stop": 0.5}       # verdict-only kept


def test_protection_uses_verdict_levels_when_scanner_dropped_symbol():
    # The SLB bug: held, NOT in the latest scanner bridge, but Tony has a verdict -> must protect.
    positions = [{"symbol": "SLB", "qty": 10.0, "avg_entry_price": 58.0}]
    merged = ap._merge_levels(
        ap._verdict_levels([{"symbol": "SLB", "date": "2026-06-03", "target": 62.0, "stop": 55.0}]),
        {},  # scanner dropped SLB
    )
    assert ap.positions_needing_protection(positions, [], merged) == [
        {"symbol": "SLB", "qty": 10, "target": 62.0, "stop": 55.0}]


def test_fallback_protects_naked_position_with_no_levels():
    positions = [{"symbol": "ORPH", "qty": 4.0, "avg_entry_price": 100.0}]
    need = ap.positions_needing_protection(positions, [], {}, fallback_pct=(0.12, 0.20))
    assert len(need) == 1
    n = need[0]
    assert n["symbol"] == "ORPH" and n["qty"] == 4
    assert n["stop"] == 88.0 and n["target"] == 120.0  # 100*(1-.12) / 100*(1+.20)
    assert n["target"] > n["stop"]


def test_no_fallback_preserves_old_skip_when_no_levels():
    positions = [{"symbol": "ORPH", "qty": 4.0, "avg_entry_price": 100.0}]
    assert ap.positions_needing_protection(positions, [], {}) == []  # default off -> old behavior


def test_fallback_skips_when_entry_price_unknown():
    positions = [{"symbol": "ORPH", "qty": 4.0}]  # no avg_entry_price
    assert ap.positions_needing_protection(positions, [], {}, fallback_pct=(0.12, 0.20)) == []
