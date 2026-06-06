from runner.main import _build_recap_lines


def test_recap_lines_full():
    acct = {
        "equity": 1_010_000.0, "last_equity": 1_000_000.0,
        "open_positions": [
            {"symbol": "A", "unrealized_pl": 250.0},
            {"symbol": "B", "unrealized_pl": -50.0},
        ],
    }
    rec = {"win_rate": 62.5, "graded": 8}
    realized = {"today": {"count": 3, "wins": 2, "losses": 1, "realized_pl": 420.0},
                "all_time": {}}
    lines = _build_recap_lines(acct, rec, realized)
    assert lines[0].startswith("Equity: $1,010,000")
    assert "▲" in lines[0] and "$10,000" in lines[0] and "+1.00%" in lines[0]
    assert lines[1] == "Open: 2 positions · unrealized P/L $200.00"
    assert lines[2] == "Closed today: 3  (2 win / 1 loss) · realized P/L $420.00"
    # the graded metric is RELABELED — must never read as Tony's own trade record
    assert lines[3] == "Scanner-verdict accuracy: 62.5% (8)"
    assert "win-rate" not in lines[3].lower()


def test_recap_lines_down_day_and_no_winrate():
    acct = {"equity": 990_000.0, "last_equity": 1_000_000.0, "open_positions": []}
    rec = {"win_rate": None, "graded": 0}
    realized = {"today": {"count": 0, "wins": 0, "losses": 0, "realized_pl": 0.0}}
    lines = _build_recap_lines(acct, rec, realized)
    assert "▼" in lines[0] and "-1.00%" in lines[0]
    assert lines[1] == "Open: 0 positions · unrealized P/L $0.00"
    assert lines[3] == "Scanner-verdict accuracy: n/a yet"


def test_recap_lines_equity_na():
    lines = _build_recap_lines({"open_positions": []}, {"win_rate": None, "graded": 0},
                               {"today": {"count": 0, "wins": 0, "losses": 0, "realized_pl": 0.0}})
    assert lines[0] == "Equity: n/a"
