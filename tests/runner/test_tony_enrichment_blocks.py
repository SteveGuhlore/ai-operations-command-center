"""Tier-A brief enrichments: book visibility, lessons feedback, regime header, execution feedback.
All read-only / cache-backed / fail-soft — they must enrich a brief when data exists and vanish
cleanly (empty string) when it doesn't, so they never block brief creation or the trading loop.
"""
import json

from runner.tools import tony_book as tb
from runner.tools import tony_outcomes as to
from runner.tools import market_regime as mr
from runner.ledger import tony_scorecard as tsc


# ----------------------------- A1: book visibility -----------------------------

def test_attach_protection_marks_naked_and_levels():
    positions = [{"symbol": "AAA", "qty": 10, "avg_entry_price": 50.0, "current_price": 52.0,
                  "unrealized_pl": 20.0, "unrealized_plpc": 0.04},
                 {"symbol": "BBB", "qty": 5, "avg_entry_price": 30.0, "current_price": 29.0,
                  "unrealized_pl": -5.0, "unrealized_plpc": -0.033}]
    orders = [{"symbol": "AAA", "side": "sell", "limit_price": 58.0, "stop_price": None},
              {"symbol": "AAA", "side": "sell", "limit_price": None, "stop_price": 47.0}]
    out = {p["symbol"]: p for p in tb.attach_protection(positions, orders)}
    assert out["AAA"]["target"] == 58.0 and out["AAA"]["stop"] == 47.0 and out["AAA"]["protected"]
    assert out["BBB"]["protected"] is False  # no sell legs -> naked


def test_book_block_renders_and_flags_naked(tmp_path, monkeypatch):
    cache = {"ts": "2026-06-05T16:00:00", "status": "ok", "equity": 999000.0, "cash": 120000.0,
             "positions": [{"symbol": "AAA", "qty": 10, "avg_entry_price": 50.0, "current_price": 52.0,
                            "unrealized_pl": 20.0, "unrealized_plpc": 0.04, "stop": 47.0,
                            "target": 58.0, "protected": True},
                           {"symbol": "NKD", "qty": 3, "avg_entry_price": 30.0, "current_price": 29.0,
                            "unrealized_pl": -3.0, "unrealized_plpc": -0.033, "stop": None,
                            "target": None, "protected": False}]}
    cf = tmp_path / "book.json"
    cf.write_text(json.dumps(cache))
    monkeypatch.setenv("TONY_BOOK_CACHE", str(cf))
    block = tb.book_block()
    assert "Your Current Book" in block
    assert "$999,000" in block and "AAA" in block
    assert "NAKED" in block  # the unprotected position is flagged


def test_book_block_empty_without_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_BOOK_CACHE", str(tmp_path / "nope.json"))
    assert tb.book_block() == ""  # missing cache -> brief simply omits the section


def test_write_book_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_BOOK_CACHE", str(tmp_path / "book.json"))

    class _Broker:
        def account(self):
            return {"equity": 1000.0, "last_equity": 1000.0, "cash": 500.0,
                    "open_positions": [{"symbol": "AAA", "qty": 2, "avg_entry_price": 10.0,
                                        "current_price": 11.0, "unrealized_pl": 2.0, "unrealized_plpc": 0.1}]}

        def open_orders(self):
            return [{"symbol": "AAA", "side": "sell", "limit_price": 12.0, "stop_price": 9.0}]

    cache = tb.write_book_cache(_Broker())
    assert cache["status"] == "ok" and cache["positions"][0]["target"] == 12.0
    assert tb.read_book_cache()["positions"][0]["stop"] == 9.0


def test_get_tony_book_degrades_without_keys(monkeypatch):
    monkeypatch.setattr("runner.ledger.alpaca_paper.paper_book",
                        lambda: {"status": "no_keys", "open_positions": [], "orders": []})
    assert tb.get_tony_book()["status"] == "no_keys"


# ----------------------------- A4: execution feedback -----------------------------

def test_summarize_execution_covers_each_state():
    verdicts = [
        {"date": "2026-06-05", "symbol": "FILL", "verdict": "reaffirm", "target": 60, "stop": 50},
        {"date": "2026-06-05", "symbol": "BAD", "verdict": "adjust", "target": 40, "stop": 50},
        {"date": "2026-06-05", "symbol": "WAIT", "verdict": "override", "target": 60, "stop": 50},
        {"date": "2026-06-05", "symbol": "GONE", "verdict": "close"},
        {"date": "2026-06-05", "symbol": "STUCK", "verdict": "close"},
    ]
    executed = {"2026-06-05:FILL:open", "2026-06-05:GONE:close", "2026-06-05:STUCK:close"}
    held = {"FILL", "STUCK"}
    lines = "\n".join(tb.summarize_execution(verdicts, executed, held))
    assert "FILL (reaffirm) filled — in your book" in lines
    assert "BAD (adjust) NOT executed — target ≤ stop" in lines
    assert "WAIT (override) not executed yet" in lines
    assert "GONE close executed — flattened" in lines
    assert "STUCK close executed — ⚠️ STILL HELD" in lines  # close that didn't flatten is surfaced


def test_execution_feedback_block_wires_files(tmp_path, monkeypatch):
    (tmp_path / "v.json").write_text(json.dumps(
        [{"date": "2026-06-05", "symbol": "FILL", "verdict": "reaffirm", "target": 60, "stop": 50}]))
    (tmp_path / "e.json").write_text(json.dumps(["2026-06-05:FILL:open"]))
    (tmp_path / "book.json").write_text(json.dumps(
        {"status": "ok", "positions": [{"symbol": "FILL", "qty": 5}]}))
    monkeypatch.setenv("TONY_VERDICTS_FILE", str(tmp_path / "v.json"))
    monkeypatch.setenv("TONY_EXECUTED_LOG", str(tmp_path / "e.json"))
    monkeypatch.setenv("TONY_BOOK_CACHE", str(tmp_path / "book.json"))
    block = tb.execution_feedback_block()
    assert "Execution Feedback" in block and "FILL (reaffirm) filled" in block


def test_execution_feedback_empty_without_verdicts(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_VERDICTS_FILE", str(tmp_path / "none.json"))
    assert tb.execution_feedback_block() == ""


# ----------------------------- A2: lessons feedback -----------------------------

def test_lessons_block_surfaces_edges_and_library(tmp_path, monkeypatch):
    # 6 winners on a tag -> an edge above the n>=5 floor; library bullets get excerpted.
    verdicts = [{"date": "2026-06-01", "symbol": f"W{i}", "verdict": "reaffirm", "stop": 90.0,
                 "confidence": "high", "evidence": ["clean_breakout"]} for i in range(6)]
    outcomes = [{"symbol": f"W{i}", "pick_date": "2026-06-01", "result": "target_hit",
                 "return_pct": 5.0} for i in range(6)]
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    (tmp_path / "o.json").write_text(json.dumps(outcomes))
    lib = tmp_path / "pattern-library.md"
    lib.write_text("# Patterns\n- Fade earnings-in-window longs; they stop out.\n")
    # discover_edges resolves VERDICTS/OUTCOMES as scorecard module constants (import-time);
    # patch the attrs directly, the way test_tony_scorecard does.
    monkeypatch.setattr(tsc, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(tsc, "OUTCOMES_FILE", tmp_path / "o.json")
    monkeypatch.setenv("TONY_PATTERN_LIBRARY", str(lib))
    block = to.lessons_block(min_edge_n=5)
    assert "Lessons From Your Own Record" in block
    assert "clean_breakout 100.0% (n=6)" in block
    assert "Fade earnings-in-window longs" in block


def test_lessons_block_empty_without_data(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_VERDICTS_FILE", str(tmp_path / "v.json"))
    monkeypatch.setenv("TONY_OUTCOMES_FILE", str(tmp_path / "o.json"))
    monkeypatch.setenv("TONY_PATTERN_LIBRARY", str(tmp_path / "lib.md"))
    assert to.lessons_block() == ""


# ----------------------------- A3: regime header -----------------------------

def test_refresh_and_header_from_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_REGIME_CACHE", str(tmp_path / "regime.json"))
    monkeypatch.setattr(mr, "get_market_regime", lambda: {
        "regime": "risk_off", "vix": 28.3, "spy_above_sma50": False,
        "leaders": ["Energy (XLE)", "Staples (XLP)"],
        "rates": {"dgs10": 4.3, "dgs2": 4.6, "spread_2s10s": -0.3, "curve": "inverted"},
        "macro_flags": ["yield_curve_inverted"]})
    assert mr.cache_stale()  # no cache yet
    mr.refresh_regime_cache()
    assert not mr.cache_stale()  # fresh now
    header = mr.regime_header()
    assert "risk_off" in header and "VIX 28.3" in header
    assert "2s10s inverted" in header and "yield_curve_inverted" in header


def test_refresh_keeps_last_good_on_error(tmp_path, monkeypatch):
    cf = tmp_path / "regime.json"
    cf.write_text(json.dumps({"ts": "2000-01-01T00:00:00", "regime": "risk_on", "vix": 12.0}))
    monkeypatch.setenv("TONY_REGIME_CACHE", str(cf))
    monkeypatch.setattr(mr, "get_market_regime", lambda: {"error": "yfinance down"})
    out = mr.refresh_regime_cache()       # stale + fetch errors -> keep the old cache
    assert out["regime"] == "risk_on"


def test_regime_header_empty_without_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("TONY_REGIME_CACHE", str(tmp_path / "none.json"))
    assert mr.regime_header() == ""


# ----------------------------- end-to-end: blocks land in a real brief -----------------------------

def test_daily_brief_embeds_book_and_regime(tmp_path, monkeypatch):
    from runner.bridge import tony_bridge as bridge
    bridge_dir = tmp_path / "bridge"
    tasks_dir = tmp_path / "tasks"
    bridge_dir.mkdir()
    tasks_dir.mkdir()
    monkeypatch.setattr(bridge, "BRIDGE_MD_DIR", bridge_dir)
    monkeypatch.setattr(bridge, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(bridge, "VAULT_DIR", tmp_path / "vault")
    monkeypatch.setattr(bridge, "_PROCESSED_LOG", tmp_path / "processed.json")
    monkeypatch.setattr(bridge, "TRADING_REPORTS_DIR", tmp_path / "reports")

    (tmp_path / "book.json").write_text(json.dumps(
        {"ts": "2026-06-05T16:00:00", "status": "ok", "equity": 999000.0, "cash": 100.0,
         "positions": [{"symbol": "AAA", "qty": 10, "avg_entry_price": 50.0, "current_price": 52.0,
                        "unrealized_pl": 20.0, "unrealized_plpc": 0.04, "stop": 47.0,
                        "target": 58.0, "protected": True}]}))
    (tmp_path / "regime.json").write_text(json.dumps(
        {"ts": "2026-06-05T09:00:00", "regime": "risk_off", "vix": 28.3, "spy_above_sma50": False}))
    monkeypatch.setenv("TONY_BOOK_CACHE", str(tmp_path / "book.json"))
    monkeypatch.setenv("TONY_REGIME_CACHE", str(tmp_path / "regime.json"))

    (bridge_dir / "2026-06-05.md").write_text(
        "---\ndate: 2026-06-05\n---\n\n## Tier 1\n### [[AAA]]\nScore 88\n", encoding="utf-8")
    bridge.scan_and_process()

    body = (tasks_dir / "TONY-DAILY-BRIEF-20260605.md").read_text(encoding="utf-8")
    assert "Your Current Book" in body and "AAA" in body
    assert "Macro Regime" in body and "risk_off" in body
