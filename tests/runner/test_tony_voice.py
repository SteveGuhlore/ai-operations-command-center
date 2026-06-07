from runner.tools import tony_voice as v


def test_record_row_and_page():
    rows = [{"symbol": "FCX", "realized_pl": -462.2, "pct": -3.1, "reason": "stop", "date": "2026-06-05"},
            {"symbol": "NVDA", "realized_pl": 924.0, "pct": 6.2, "reason": "target", "date": "2026-06-04"}]
    line = v._record_row(rows[0])
    assert "FCX" in line and "462" in line and "stop" in line.lower()
    realized = {"all_time": {"count": 2, "wins": 1, "losses": 1, "realized_pl": 461.8,
                             "by_reason": {"stop": 1, "target": 1}}}
    page = v.say_record_page(rows, realized, page=0, page_size=12)
    assert "track record" in page["text"].lower()
    assert "FCX" in page["text"] and "NVDA" in page["text"]
    assert page["has_more"] is False
    many = [dict(rows[0], symbol=f"S{i}") for i in range(13)]
    p0 = v.say_record_page(many, realized, page=0, page_size=12)
    assert p0["has_more"] is True and p0["text"].count("\n") >= 12
    p1 = v.say_record_page(many, realized, page=1, page_size=12)
    assert "S12" in p1["text"] and p1["has_more"] is False


def test_entry_first_person_with_thesis():
    s = v.say_entry("NVDA", 66, 100.0, 94.0, 115.0, 1.0, reason="breakout over $99 on heavy volume")
    assert s.startswith("🟢")
    assert "I bought NVDA" in s
    assert "$100.00" in s and "$115.00" in s and "$94.00" in s
    assert "1% of the account" in s
    assert "Why: breakout over $99 on heavy volume" in s
    assert "66 sh" in s


def test_entry_without_thesis_omits_why():
    s = v.say_entry("FCX", 50, 45.0, 41.0, 55.0, 2.0)
    assert "Why:" not in s
    assert "2% of the account" in s


def test_exit_target_win_shows_r_multiple():
    s = v.say_exit("NVDA", 66, 114.0, 924.0, reason="target", r_mult=2.3)
    assert s.startswith("🟩")
    assert "I sold NVDA for a +$924 win" in s
    assert "price target" in s and "2.3×" in s


def test_exit_stop_loss_phrasing():
    s = v.say_exit("FCX", 50, 41.0, -200.0, reason="stop")
    assert s.startswith("🟥")
    assert "I sold FCX for a $200 loss" in s
    assert "safety stop" in s
    assert "-$" not in s  # loss is worded, not signed


def test_exit_discretionary_close():
    s = v.say_exit("AAPL", 10, 150.0, 50.0, reason="close")
    assert "stepped aside" in s


def test_reprice_first_person():
    s = v.say_reprice("FCX", 152, 74.62, 61.88)
    assert "I adjusted FCX" in s
    assert "stop $61.88" in s and "target $74.62" in s


def test_daily_header_up_down_flat():
    assert "up $" in v.say_daily_header(101000, 1200)
    assert "gave back $" in v.say_daily_header(99000, -800)
    assert "flat" in v.say_daily_header(100000, 0)
    assert v.say_daily_header(100000, None).startswith("📊")
