"""tandem_sandbox — run CC's half of the bot<->CC handoff test in TOTAL isolation.

Safety is the whole point of this script:
  1. It snapshots a checksum of every real file the test could plausibly touch BEFORE running.
  2. It redirects EVERY CC writer (bridge, verdicts, record, ledger, tasks, equity, processed
     log) into a throwaway sandbox via env + module overrides — set BEFORE importing CC code,
     then *verified* (it aborts if any path still points at production).
  3. It runs the ingest -> track-record -> verdict -> record chain against the sandbox only.
  4. In a finally block it DELETES the sandbox and re-checksums the real files: if a single
     real byte changed, it fails loudly. No order is ever placed (TONY_LIVE_ENABLED stays unset).

Usage:
  python scripts/tandem_sandbox.py            # uses the scanner's bridge already in the sandbox
  python scripts/tandem_sandbox.py --self-test # generates its own fake bridge+outcomes (no scanner)
  python scripts/tandem_sandbox.py --root C:\\Users\\alexa\\Downloads\\tandem-sandbox
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOT_REPORTS = REPO.parent / "TradingBotAgentProject" / "reports"
sys.path.insert(0, str(REPO))

# Real files/dirs that must be byte-for-byte unchanged after the test.
PROTECTED_FILES = [
    REPO / "vault" / "tony-stocks" / "signal-ledger.md",
    REPO / "vault" / "tony-stocks" / "tony_stocks_record.json",
    REPO / "workspace" / "equity-history.json",
    REPO / "workspace" / "logs" / "tony-bridge-processed.json",
    REPO / "workspace" / "alpaca-executed.json",
    REPO / "workspace" / "notify-state.json",
    REPO / ".env",
    BOT_REPORTS / "tony_stocks_outcomes.json",
    BOT_REPORTS / "tony_stocks_verdicts.json",
    BOT_REPORTS / "tony_stocks_record.json",
]
PROTECTED_DIRS = [
    REPO / "workspace" / "tasks" / "todo",
    REPO / "workspace" / "tasks" / "done",
]


def _hash(p: Path) -> str:
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except (OSError, FileNotFoundError):
        return "MISSING"


def _snapshot() -> dict:
    snap = {str(p): _hash(p) for p in PROTECTED_FILES}
    for d in PROTECTED_DIRS:
        names = sorted(f.name for f in d.glob("*")) if d.exists() else []
        snap[str(d) + "/*"] = "|".join(names)
    return snap


def _diff(before: dict, after: dict) -> list:
    return [k for k in before if before.get(k) != after.get(k)]


def _wire_env(root: Path) -> dict:
    """Point every CC writer at the sandbox. MUST run before importing CC modules (several read
    their file paths from env at import time)."""
    reports = root / "reports"
    paths = {
        "TONY_BRIDGE_DIR": root / "bridge" / "tony-stocks",
        "TONY_OUTCOMES_FILE": reports / "tony_stocks_outcomes.json",
        "TONY_VERDICTS_FILE": reports / "tony_stocks_verdicts.json",
        "TONY_RECORD_FILE": reports / "tony_stocks_record.json",
        "TONY_VAULT_RECORD_FILE": root / "vault" / "tony-stocks" / "tony_stocks_record.json",
        "TONY_REPORTS_DIR": reports,
        "TONY_EQUITY_HISTORY": root / "equity-history.json",
    }
    for k, v in paths.items():
        os.environ[k] = str(v)
    os.environ.pop("TONY_LIVE_ENABLED", None)  # never place an order
    (root / "bridge" / "tony-stocks").mkdir(parents=True, exist_ok=True)
    (reports).mkdir(parents=True, exist_ok=True)
    (root / "vault" / "tony-stocks").mkdir(parents=True, exist_ok=True)
    (root / "tasks").mkdir(parents=True, exist_ok=True)
    return paths


def _verify_isolation(root: Path):
    """Abort BEFORE doing anything if any CC path still resolves to production."""
    from runner.bridge import tony_bridge as tb
    from runner.ledger import tony_scorecard as sc
    from runner.tools import tony_verdict as tv

    tb.TASKS_DIR = root / "tasks"
    tb.VAULT_DIR = root / "vault"
    tb._PROCESSED_LOG = root / "processed.json"

    checks = {
        "tony_bridge.BRIDGE_MD_DIR": tb.BRIDGE_MD_DIR,
        "tony_bridge.TASKS_DIR": tb.TASKS_DIR,
        "tony_bridge.VAULT_DIR": tb.VAULT_DIR,
        "scorecard.VERDICTS_FILE": sc.VERDICTS_FILE,
        "scorecard.OUTCOMES_FILE": sc.OUTCOMES_FILE,
        "scorecard.RECORD_FILE": sc.RECORD_FILE,
        "scorecard.VAULT_RECORD_FILE": sc.VAULT_RECORD_FILE,
        "tony_verdict.VERDICTS_FILE": tv.VERDICTS_FILE,
    }
    root_s = str(root)
    leaks = {name: str(p) for name, p in checks.items() if root_s not in str(p)}
    if leaks:
        raise SystemExit("ABORT — these CC paths are NOT inside the sandbox:\n"
                         + "\n".join(f"  {n}: {p}" for n, p in leaks.items()))
    return tb, sc, tv


def _seed_self_test(root: Path):
    today = str(date.today())
    bridge = root / "bridge" / "tony-stocks" / f"{today}.md"
    bridge.write_text(f"""---
date: {today}
source: TradingBotAgentProject
strategy_version: v1
export_type: eod-bridge
---

# Tony Stocks Bridge — {today} — EOD (SANDBOX SELF-TEST — DELETE AFTER)

## Scanner Summary
- Universe: 548 | Scored: 3 | Cycles: 1

## Tier 1 — Hand Off for Deep Analysis
### [[NVDA]]
- Days active: 4 | Score: 99.9 | Setup: Breakout Watch
- Last close: $100.00 | Target: $115.00 (+15.0%) | Stop: $94.00 (-6.0%)
- R/R: 2.5:1 | Entry triggered: yes
### [[AMD]]
- Days active: 3 | Score: 88.8 | Setup: Momentum Continuation
- Last close: $150.00 | Target: $168.00 (+12.0%) | Stop: $141.00 (-6.0%)
- R/R: 2.0:1 | Entry triggered: no
### [[PINS]]
- Days active: 3 | Score: 85.0 | Setup: Breakout Watch
- Last close: $30.00 | Target: $34.00 (+13.3%) | Stop: $28.00 (-6.7%)
- R/R: 2.0:1 | Entry triggered: yes
""", encoding="utf-8")
    outcomes = [
        {"symbol": "NVDA", "pick_date": "2026-05-20", "result": "target_hit", "entry": 90.0,
         "exit": 104.0, "return_pct": 15.5, "days_held": 7, "resolved_date": "2026-05-27"},
        {"symbol": "AMD", "pick_date": "2026-05-21", "result": "stop_hit", "entry": 160.0,
         "exit": 150.0, "return_pct": -6.2, "days_held": 4, "resolved_date": "2026-05-25"},
        {"symbol": "PINS", "pick_date": "2026-05-22", "result": "target_hit", "entry": 28.0,
         "exit": 32.0, "return_pct": 14.3, "days_held": 6, "resolved_date": "2026-05-28"},
        {"symbol": "FCX", "pick_date": "2026-05-19", "result": "closed", "entry": None,
         "exit": None, "return_pct": None, "days_held": None, "resolved_date": "2026-05-26"},
    ]
    (root / "reports" / "tony_stocks_outcomes.json").write_text(json.dumps(outcomes, indent=2),
                                                                encoding="utf-8")
    return today, bridge


def _check_apis() -> dict:
    """Live, READ-ONLY checks that every external integration/key actually works (+ one real
    Telegram send). Loads real keys from .env; never writes to a trading account."""
    from dotenv import load_dotenv
    load_dotenv()
    r = {}

    def _try(name, fn):
        try:
            r[name] = fn()
        except Exception as exc:
            r[name] = f"ERR {exc}"

    from runner.ledger.equity_history import _latest_prices
    from runner.ledger.alpaca_paper import account_record
    from runner.tools.stock_data import _finnhub_enrich, get_stock_data
    from runner.tools.stock_catalysts import _load_cik_map
    from runner.tools.market_regime import _fred_yields
    from runner.tools.stock_news import get_stock_news
    from runner.tools.notify import notify

    _try("alpaca_data", lambda: bool(_latest_prices(["AAPL"])))
    _try("alpaca_trading_auth", lambda: account_record().get("status") == "ok")
    _try("finnhub", lambda: bool(_finnhub_enrich("AAPL")))
    _try("sec_edgar", lambda: len(_load_cik_map()) > 1000)
    _try("fred", lambda: _fred_yields() is not None)
    _try("yfinance", lambda: "price" in get_stock_data("AAPL"))
    _try("alpaca_news", lambda: get_stock_news("AAPL", limit=2).get("count", 0) >= 0)

    def _tg():
        import httpx
        tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        ok = httpx.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=10).json().get("ok", False)
        sent = notify("🧪 tandem-test: live API + notification check OK").get("sent", False)
        return bool(ok and sent)
    _try("telegram", _tg)
    return r


def _test_execution_and_notify(root: Path) -> bool:
    """Exercise the FULL execution + notification path with a MOCK Alpaca broker — plan -> risk
    sizing -> bracket -> entry alert, and a position-diff -> exit alert. ZERO real orders."""
    import runner.ledger.alpaca_paper as ap
    import runner.tools.notify as nf

    ap.EXECUTED_LOG = root / "alpaca-executed.json"
    ap.NOTIFY_STATE = root / "notify-state.json"
    captured = []
    nf.notify = lambda text, **k: (captured.append(text), {"sent": True})[1]

    class _Mock:
        def __init__(self):
            self.calls = []
            self._pos = []
        def _latest_price(self, s):
            return 100.0
        def account(self):
            return {"equity": 1_000_000.0, "open_positions": list(self._pos)}
        def buy(self, symbol, notional, target, stop):
            self.calls.append(("buy", symbol))
            self._pos.append({"symbol": symbol, "qty": 10, "avg_entry_price": 100.0})
            return {"qty": 10, "entry": 100.0}
        def close(self, symbol):
            self.calls.append(("close", symbol))
            self._pos = [p for p in self._pos if p["symbol"] != symbol]
        def open_orders(self):
            return []
        def protect(self, *a, **k):
            pass
        def reprice(self, *a, **k):
            pass
        def cancel_entry_orders(self):
            return 0

    # a fresh buy verdict in the sandbox -> sync should size + bracket + alert
    (root / "reports" / "tony_stocks_verdicts.json").write_text(json.dumps([
        {"date": str(date.today()), "symbol": "TSLA", "verdict": "reaffirm",
         "tony_score": 90, "target": 120.0, "stop": 90.0, "confidence": "high"}
    ]), encoding="utf-8")
    mock = _Mock()
    ap.sync(broker=mock)
    entry_ok = ("buy", "TSLA") in mock.calls and any("entered TSLA" in c for c in captured)

    # simulate a position that closed since last cycle -> exit alert
    (root / "notify-state.json").write_text(json.dumps(
        [{"symbol": "AAA", "qty": 10, "avg_entry_price": 50.0}]), encoding="utf-8")
    ap._notify_closed(_Mock())  # AAA absent from the (empty) positions -> AAA closed
    exit_ok = any("closed AAA" in c for c in captured)

    print(f"      buy placed: {('buy', 'TSLA') in mock.calls} · entry alert: "
          f"{any('entered TSLA' in c for c in captured)} · exit alert: {exit_ok} · "
          f"real orders: 0 (mock broker)")
    return entry_ok and exit_ok


def run(root: Path, self_test: bool) -> int:
    assert "tandem-sandbox" in str(root).lower(), "refusing to run outside a 'tandem-sandbox' dir"
    print(f"== Tandem sandbox @ {root} (self_test={self_test}) ==")

    before = _snapshot()
    print(f"[0] baseline checksums recorded for {len(before)} protected paths")

    if root.exists():
        shutil.rmtree(root)
    _wire_env(root)
    tb, sc, tv = _verify_isolation(root)
    print("[1] isolation verified — every CC writer points inside the sandbox")

    ok = True
    try:
        if self_test:
            today, bridge_file = _seed_self_test(root)
        else:
            mds = sorted(p for p in (root / "bridge" / "tony-stocks").glob("*.md"))
            if not mds:
                raise SystemExit("No bridge .md in the sandbox — have the scanner write one first, "
                                 "or pass --self-test.")
            bridge_file = mds[-1]
            today = bridge_file.stem[:10]
        print(f"[2] bridge: {bridge_file.name}")

        # --- Ingest (bot -> CC) ---
        tb._make_brief_from_bridge(bridge_file.stem, bridge_file.read_text(encoding="utf-8"))
        tasks = sorted((root / "tasks").glob("TONY-*.md"))
        ledger = root / "vault" / "tony-stocks" / "signal-ledger.md"
        print(f"[3] ingest -> {len(tasks)} task(s) created; ledger written: {ledger.exists()}")
        ok &= bool(tasks) and ledger.exists()

        # --- Tool layer: track record from the fake outcomes ---
        from runner.tools.tony_outcomes import track_record_block
        block = track_record_block()
        print(f"[4] track-record block rendered: {'Track Record' in block}")
        ok &= "Track Record" in block

        # --- CC -> bot: simulate Tony's verdicts, then the record ---
        tv.write_tony_verdict("NVDA", 92, "reaffirm", "Sandbox: breakout intact.",
                              scanner_score=99.9, target=115.0, stop=94.0,
                              evidence=["clean_breakout"], confidence="high")
        tv.write_tony_verdict("AMD", 70, "pass", "Sandbox: momentum fading, skip.",
                              scanner_score=88.8, confidence="low")
        verdicts = json.loads((root / "reports" / "tony_stocks_verdicts.json").read_text())
        has_reasoning = all("tony_reasoning" in v for v in verdicts)
        print(f"[5] verdicts written: {len(verdicts)}; tony_reasoning present: {has_reasoning}")
        ok &= len(verdicts) == 2 and has_reasoning

        rec = sc.write_record()
        need = {"win_rate", "avg_pl_per_trade", "target_hits", "stop_hits", "equity_curve", "agreement"}
        agree_keys = set(rec.get("agreement", {}))
        schema_ok = need <= set(rec) and agree_keys == {
            "agreed_right", "agreed_wrong", "cc_overrode_saved", "cc_overrode_missed"}
        print(f"[6] record written: status={rec.get('status')}; bot-contract schema ok: {schema_ok}")
        ok &= schema_ok

        # --- Every external key/integration (live, read-only) + a real Telegram send ---
        apis = _check_apis()
        print("[8] API / key checks (live):")
        for k, v in apis.items():
            print(f"      {k}: {v}")
        ok &= not any(isinstance(v, str) and v.startswith("ERR") for v in apis.values())

        # --- Full execution + notification path via a MOCK broker (no real orders) ---
        print("[9] execution + notification integration (mock broker):")
        exec_ok = _test_execution_and_notify(root)
        ok &= exec_ok
    except Exception as exc:
        ok = False
        print(f"[!] run error: {exc}")
    finally:
        # --- Teardown: always delete the sandbox, then prove production is untouched ---
        if root.exists() and "tandem-sandbox" in str(root).lower():
            shutil.rmtree(root, ignore_errors=True)
        removed = not root.exists()
        after = _snapshot()
        changed = _diff(before, after)
        print(f"\n[7] sandbox deleted: {removed}")
        if changed:
            print("[7] !! PRODUCTION FILES CHANGED — CORRUPTION:")
            for c in changed:
                print(f"      {c}")
        else:
            print("[7] production files byte-for-byte UNCHANGED")

    passed = ok and removed and not changed
    print("\n==", "PASS — tandem chain works, nothing corrupted, sandbox cleaned"
          if passed else "FAIL — see above", "==")
    return 0 if passed else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(REPO.parent / "tandem-sandbox"))
    ap.add_argument("--self-test", action="store_true",
                    help="generate a fake bridge+outcomes instead of using the scanner's")
    args = ap.parse_args()
    sys.exit(run(Path(args.root), args.self_test))


if __name__ == "__main__":
    main()
