"""Round-2 audit stress tests: close-retry semantics, reaper liveness, pre-open dedup,
research-wave state atomicity, tier dedup, outreach IO hardening (email/DM/places/web/inbox),
and the end-to-end bot -> CC -> broker -> feedback pipeline ("works in tandem" proof).
"""
import json
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner.bridge import tony_bridge as bridge
from runner.bridge import research_wave as rw
from runner.ledger import alpaca_paper as ap
from runner.tasks import locker
from runner.tools import email_sender as es
from runner.tools import social_dm as dm
from runner.tools import inbox_reader as ir
from runner.tools.web import _extract_business_contact_info, _is_captcha_response, _TextExtractor


# ----------------------------------------------------------------- close(): retry semantics

class _CloseBroker:
    """Broker stub for sync(): close() behavior is injectable."""
    def __init__(self, close_exc=None):
        self.close_exc = close_exc
        self.closed = []

    def filled_orders(self, limit=200):
        return []

    def buy(self, *a, **k):
        return {"qty": 1, "entry": 100.0}

    def close(self, symbol):
        self.closed.append(symbol)
        if self.close_exc:
            raise self.close_exc

    def protect(self, *a, **k):
        pass

    def reprice(self, *a, **k):
        pass

    def account(self):
        return {"equity": 1_000_000.0, "cash": 1.0, "last_equity": 1_000_000.0,
                "open_positions": [{"symbol": "XXX", "qty": 10, "avg_entry_price": 100.0,
                                    "current_price": 99.0, "unrealized_pl": -10.0,
                                    "unrealized_plpc": -0.001}]}

    def open_orders(self):
        return []


def _wire_sync(tmp_path, monkeypatch, verdicts):
    (tmp_path / "v.json").write_text(json.dumps(verdicts))
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    monkeypatch.setattr(ap, "_latest_scanner_levels", lambda: {})
    monkeypatch.setenv("TONY_MARKET_SESSION", "open")
    monkeypatch.setenv("TONY_BOOK_CACHE", str(tmp_path / "book.json"))


def test_failed_close_is_not_marked_done(tmp_path, monkeypatch):
    _wire_sync(tmp_path, monkeypatch,
               [{"date": "2026-06-09", "symbol": "XXX", "verdict": "close"}])
    b = _CloseBroker(close_exc=RuntimeError("403 forbidden"))
    ap.sync(broker=b)
    done = json.loads((tmp_path / "exec.json").read_text())
    # the close raised -> key NOT recorded -> next cycle retries instead of silent no-op forever
    assert "2026-06-09:XXX:close" not in done


def test_successful_close_is_marked_done(tmp_path, monkeypatch):
    _wire_sync(tmp_path, monkeypatch,
               [{"date": "2026-06-09", "symbol": "XXX", "verdict": "close"}])
    b = _CloseBroker()
    ap.sync(broker=b)
    done = json.loads((tmp_path / "exec.json").read_text())
    assert "2026-06-09:XXX:close" in done and b.closed == ["XXX"]


# ----------------------------------------------------------------- buy(): defer without price

def test_sync_retries_buy_when_price_missing(tmp_path, monkeypatch):
    _wire_sync(tmp_path, monkeypatch,
               [{"date": "2026-06-09", "symbol": "NOPX", "verdict": "override",
                 "target": 30, "stop": 25}])

    class _NoPriceBroker(_CloseBroker):
        def buy(self, *a, **k):
            raise ValueError("no live price for NOPX; deferring bracket entry")

    ap.sync(broker=_NoPriceBroker())
    done = json.loads((tmp_path / "exec.json").read_text())
    assert "2026-06-09:NOPX:open" not in done  # left unmarked -> retried next cycle


# ----------------------------------------------------------------- reaper: pid liveness

def _mk_stale_task(ws: Path, task_id: str, age_s: float):
    ip = ws / "tasks" / "in_progress"
    ip.mkdir(parents=True, exist_ok=True)
    f = ip / f"{task_id}.md"
    f.write_text(f"---\ntask_id: {task_id}\nstatus: in_progress\n---\nbody\n", encoding="utf-8")
    old = time.time() - age_s
    os.utime(f, (old, old))
    return f


def test_reaper_spares_task_with_live_owner(tmp_path, monkeypatch):
    from runner import main as m
    ws = tmp_path / "workspace"
    monkeypatch.setattr(locker, "LOCKS_DIR", ws / "locks")
    _mk_stale_task(ws, "LIVE-1", age_s=m._STALE_TASK_AGE_S + 60)
    assert locker.acquire_lock("LIVE-1", "worker")  # lock owned by THIS (alive) process
    m._reap_stale_tasks(ws)
    assert (ws / "tasks" / "in_progress" / "LIVE-1.md").exists()   # not reaped
    assert not (ws / "tasks" / "todo" / "LIVE-1.md").exists()


def test_reaper_reaps_task_with_dead_owner(tmp_path, monkeypatch):
    from runner import main as m
    ws = tmp_path / "workspace"
    monkeypatch.setattr(locker, "LOCKS_DIR", ws / "locks")
    _mk_stale_task(ws, "DEAD-1", age_s=m._STALE_TASK_AGE_S + 60)
    proc = subprocess.Popen(["true"])
    proc.wait()  # pid is now definitely dead
    (ws / "locks").mkdir(parents=True, exist_ok=True)
    (ws / "locks" / "DEAD-1.lock").write_text(
        json.dumps({"task_id": "DEAD-1", "pid": proc.pid}), encoding="utf-8")
    m._reap_stale_tasks(ws)
    assert (ws / "tasks" / "todo" / "DEAD-1.md").exists()          # requeued
    assert not (ws / "tasks" / "in_progress" / "DEAD-1.md").exists()


def test_reaper_overrides_liveness_past_hard_cap(tmp_path, monkeypatch):
    from runner import main as m
    ws = tmp_path / "workspace"
    monkeypatch.setattr(locker, "LOCKS_DIR", ws / "locks")
    _mk_stale_task(ws, "WEDGED-1", age_s=m._STALE_TASK_AGE_S * 4 + 60)
    assert locker.acquire_lock("WEDGED-1", "worker")  # live pid, but way past 4x cap
    m._reap_stale_tasks(ws)
    assert (ws / "tasks" / "todo" / "WEDGED-1.md").exists()  # reaped anyway — no forever-wedge


def test_lock_owner_alive_helper(tmp_path, monkeypatch):
    monkeypatch.setattr(locker, "LOCKS_DIR", tmp_path)
    assert locker.acquire_lock("T1", "w")
    assert locker.lock_owner_alive("T1") is True      # our own pid
    assert locker.lock_owner_alive("missing") is False


# ----------------------------------------------------------------- pre-open dedup

_PREOPEN_SETUP_BODY = "## Tier 1\n### [[AAA]]\nDays active: 5\nScore: 88\n"


def _preopen_setup(tmp_path, monkeypatch):
    tasks = tmp_path / "workspace" / "tasks" / "todo"
    tasks.mkdir(parents=True)
    bdir = tmp_path / "bridge"
    bdir.mkdir()
    monkeypatch.setattr(bridge, "TASKS_DIR", tasks)
    monkeypatch.setattr(bridge, "BRIDGE_MD_DIR", bdir)
    monkeypatch.setattr(bridge, "VAULT_DIR", tmp_path / "vault")
    return tasks


def test_preopen_deepdive_is_idempotent(tmp_path, monkeypatch):
    tasks = _preopen_setup(tmp_path, monkeypatch)
    bridge.make_preopen_deepdive("2026-06-10")
    first = (tasks / "TONY-PREOPEN-20260610.md").read_text(encoding="utf-8")
    bridge.make_preopen_deepdive("2026-06-10")  # manual re-run same day
    assert (tasks / "TONY-PREOPEN-20260610.md").read_text(encoding="utf-8") == first
    assert len(list(tasks.glob("TONY-PREOPEN-*.md"))) == 1


def test_preopen_deepdive_not_respawned_after_done(tmp_path, monkeypatch):
    tasks = _preopen_setup(tmp_path, monkeypatch)
    bridge.make_preopen_deepdive("2026-06-10")
    done = tasks.parent / "done"
    done.mkdir()
    (tasks / "TONY-PREOPEN-20260610.md").rename(done / "TONY-PREOPEN-20260610.md")
    bridge.make_preopen_deepdive("2026-06-10")  # consumed already -> must not respawn
    assert not (tasks / "TONY-PREOPEN-20260610.md").exists()


# ----------------------------------------------------------------- research-wave state

def test_research_wave_state_write_is_atomic(tmp_path, monkeypatch):
    monkeypatch.setattr(rw, "STATE_FILE", tmp_path / "state.json")
    rw._write_state({"staged_for": "2026-06-10"})
    assert rw._read_state() == {"staged_for": "2026-06-10"}
    assert not (tmp_path / "state.json.tmp").exists()


def test_research_wave_corrupt_state_degrades(tmp_path, monkeypatch):
    monkeypatch.setattr(rw, "STATE_FILE", tmp_path / "state.json")
    (tmp_path / "state.json").write_text("{ nope", encoding="utf-8")
    assert rw._read_state() == {}


# ----------------------------------------------------------------- tier dedup + regex parity

def test_symbol_in_two_tiers_enters_ledger_once():
    md = (
        "## Tier 1\n### [[DUP]]\nDays active: 4\nScore: 90\nSetup: Breakout Watch\n"
        "## Tier 2\n| [[DUP]] | 75 | Momentum | $50 |\n| [[NEW2]] | 70 | Pullback | $20 |\n"
    )
    sig = bridge._parse_bridge_signals(md)
    all_syms = [s["symbol"] for s in sig["tier1"] + sig["newer"]]
    assert all_syms.count("DUP") == 1
    assert "NEW2" in all_syms


def test_block_and_fanout_regexes_agree():
    md = "## Tier 1\n### [[GOOD.A]]\nDays active: 3\n### [[bad]]\nDays active: 3\n"
    block_syms = [m.group(1) for m in bridge._TIER1_BLOCK_RE.finditer(md)]
    fanout_syms = bridge._extract_tier1_symbols(md)
    assert block_syms == fanout_syms == ["GOOD.A"]  # one grammar, no divergence


# ----------------------------------------------------------------- email sender hardening

@pytest.fixture
def email_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTREACH_SENT_LOG", str(tmp_path / "sent.json"))
    monkeypatch.setenv("OUTREACH_EMAIL_QUEUE", str(tmp_path / "queue.md"))
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    monkeypatch.delenv("OUTREACH_AUTOMATION", raising=False)
    return tmp_path


_BODY_OK = "Hi! ... Reply STOP or unsubscribe to opt out."


@pytest.mark.parametrize("bad", ["", "  ", "not found", "N/A", "Name <a@b.com>", "hero@1x.png"])
def test_send_email_rejects_garbage_addresses(email_env, bad):
    res = es.send_email(bad, "Biz", "subj", _BODY_OK)
    assert "error" in res and not (email_env / "queue.md").exists()


def test_send_email_staging_actually_persists(email_env):
    res = es.send_email("owner@realbiz.com", "Real Biz", "Quick site question", _BODY_OK)
    assert res.get("queued") and res.get("sent") is False
    q = (email_env / "queue.md").read_text(encoding="utf-8")
    assert "owner@realbiz.com" in q and "Quick site question" in q and _BODY_OK[:20] in q


def test_send_email_never_double_contacts(email_env, monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "k")
    monkeypatch.setenv("OUTREACH_AUTOMATION", "true")

    class _R:
        status_code = 202
        text = ""

    monkeypatch.setattr(es.httpx, "post", lambda *a, **k: _R())
    assert es.send_email("owner@realbiz.com", "Biz", "s", _BODY_OK).get("success")
    second = es.send_email("Owner@RealBiz.com", "Biz", "s", _BODY_OK)  # case-insensitive
    assert "already emailed" in second.get("error", "")


def test_send_email_timeout_recorded_to_prevent_retry_double_send(email_env, monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "k")
    monkeypatch.setenv("OUTREACH_AUTOMATION", "true")

    def _boom(*a, **k):
        raise TimeoutError("read timeout")

    monkeypatch.setattr(es.httpx, "post", _boom)
    first = es.send_email("owner@realbiz.com", "Biz", "s", _BODY_OK)
    assert "UNKNOWN" in first.get("error", "")
    retry = es.send_email("owner@realbiz.com", "Biz", "s", _BODY_OK)
    assert "already emailed" in retry.get("error", "")


# ----------------------------------------------------------------- instagram dm hardening

@pytest.fixture
def dm_queue(tmp_path, monkeypatch):
    q = tmp_path / "dm-queue.md"
    monkeypatch.setattr(dm, "DM_QUEUE", q)
    monkeypatch.delenv("OUTREACH_AUTOMATION", raising=False)
    return q


@pytest.mark.parametrize("bad", ["", "@", "has spaces", "way" * 11, "héllo"])
def test_dm_rejects_garbage_handles(dm_queue, bad):
    res = dm.send_instagram_dm(bad, "Biz", "hello")
    assert "error" in res and not dm_queue.exists()


def test_dm_normalizes_pasted_url(dm_queue):
    res = dm.send_instagram_dm("https://www.instagram.com/bostonbakery/", "Boston Bakery", "hi")
    assert res.get("queued") and res["handle"] == "bostonbakery"
    assert "@bostonbakery" in dm_queue.read_text(encoding="utf-8")


def test_dm_queue_cells_sanitized(dm_queue):
    dm.send_instagram_dm("realhandle", "Bad|Pipe\nBiz", "msg", city="Lowell|MA")
    row = [l for l in dm_queue.read_text(encoding="utf-8").splitlines() if "realhandle" in l][0]
    assert row.count("|") == 6  # 5 cells -> 6 pipes; embedded pipes/newlines neutralized


# ----------------------------------------------------------------- web extraction repro cases

def test_asset_filenames_not_emails_but_real_lookalikes_kept():
    out = _extract_business_contact_info(
        "see hero@1x.png and logo@2x.png, write to info@2xsolutions.com")
    assert out["emails"] == ["info@2xsolutions.com"]


def test_words_ending_ig_do_not_mint_handles():
    out = _extract_business_contact_info("Owner: Craig Smith runs the shop. Big savings this week!")
    assert out["instagram_handles"] == []


def test_reel_url_not_a_handle_but_labeled_handle_found():
    out = _extract_business_contact_info(
        "https://www.instagram.com/reel/Cabc123xyz/ ... Instagram: bostonbakery")
    assert out["instagram_handles"] == ["@bostonbakery"]


def test_phone_not_fabricated_from_digit_runs():
    out = _extract_business_contact_info("EIN 04-3217654, founded 1998, order #555123456789")
    assert out["phones"] == []
    ok = _extract_business_contact_info("Call us at (978) 555-0142 today")
    assert ok["phones"] == ["(978) 555-0142"]


def test_plumber_copy_is_not_a_captcha():
    assert _is_captcha_response("We fix blocked drains fast. Call Boston Plumbing.") is False
    assert _is_captcha_response("Checking your browser before accessing... Cloudflare") is True


def test_text_extractor_survives_valueless_class_attr():
    p = _TextExtractor()
    p.feed('<div class><p>hello</p></div>')  # sloppy real-world HTML must not crash the fetch
    assert "hello" in " ".join(p.parts)


# ----------------------------------------------------------------- inbox reader repro cases

@pytest.mark.parametrize("body,want", [
    ("Yes, I'm interested! How much for the $499 option?\n"
     "> Easy Simple Sites offer...\n> Reply STOP or unsubscribe to opt out.", True),
    ("Never call me again, spammer.", False),
    ("Do not call me.", False),
    ("Sounds good, we have a budget for this. How much?", True),
    ("I received your email, yes I'm interested, call me", True),
    ("We already have a website, thanks.", False),
])
def test_interest_classification_repro_cases(body, want):
    assert ir._is_interested("Re: your site", body)["interested"] is want


def test_html_only_reply_is_analyzed():
    import email as email_mod
    raw = (b"Subject: Re: site\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
           b"<html><body><p>Yes, I'm <b>interested</b> &mdash; how much?</p></body></html>")
    msg = email_mod.message_from_bytes(raw)
    body = ir._body_text(msg)
    assert "interested" in body
    assert ir._is_interested("Re: site", body)["interested"] is True


# ----------------------------------------------------------------- places: unknown != no-website

def test_failed_place_detail_reads_unknown_not_no_website(monkeypatch):
    from runner.tools import places as pl
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "k")

    class _Resp:
        def __init__(self, data):
            self._d = data

        def json(self):
            return self._d

    def fake_get(url, params=None, timeout=None):
        if "textsearch" in url:
            return _Resp({"status": "OK", "results": [{"place_id": "p1", "name": "Has Site Cafe"}]})
        return _Resp({"status": "OVER_QUERY_LIMIT"})  # detail lookup fails

    monkeypatch.setattr(pl.httpx, "get", fake_get)
    out = pl.find_prospects("cafes in Salem MA")
    p = out["prospects"][0]
    assert p["has_website"] is None and "unknown" in p["website_status"]
    assert out["no_website_count"] == 0  # never counted as a no-website pitch target


# ----------------------------------------------------------------- E2E: bot -> CC -> broker -> feedback

def test_full_pipeline_bot_to_broker_to_feedback(tmp_path, monkeypatch):
    """The 'works in tandem' proof: one scanner bridge file drives the whole chain —
    ingestion -> task spawn + fan-out -> Tony's verdict -> sized/protected order via the same
    bridge's levels -> executed log -> book cache -> execution feedback Tony reads next brief."""
    from runner.tools import tony_book as tb

    # --- the bot drops a bridge file
    bridge_dir = tmp_path / "bridge" / "tony-stocks"
    tasks_dir = tmp_path / "workspace" / "tasks" / "todo"
    bridge_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)
    monkeypatch.setattr(bridge, "BRIDGE_MD_DIR", bridge_dir)
    monkeypatch.setattr(bridge, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(bridge, "TRADING_REPORTS_DIR", tmp_path / "none")
    monkeypatch.setattr(bridge, "_PROCESSED_LOG", tmp_path / "processed.json")
    monkeypatch.setattr(bridge, "VAULT_DIR", tmp_path / "vault")
    monkeypatch.setattr(bridge, "_QUIESCE_SECONDS", 0.0)
    monkeypatch.setattr(bridge, "FANOUT_MIN_TIER1", 1)  # default 3; one ticker drives this test
    from runner.ledger import deepdive_ledger as dl
    monkeypatch.setattr(dl, "LEDGER_FILE", tmp_path / "deepdive-ledger.json")  # isolate the cooldown
    (bridge_dir / "2026-06-09.md").write_text(
        "---\ndate: 2026-06-09\n---\n\n## Tier 1\n### [[AAPL]]\nDays active: 4\nScore: 91\n"
        "Setup: Momentum Continuation\nLast close: $200.00 | Target: $220.00 (+10%) | Stop: $190.00 (-5%)\n",
        encoding="utf-8")

    # --- CC ingests it: brief + per-ticker fan-out spawn
    bridge.scan_and_process()
    brief = (tasks_dir / "TONY-DAILY-BRIEF-20260609.md").read_text(encoding="utf-8")
    assert "AAPL" in brief
    assert list(tasks_dir.glob("TONY-TKR-AAPL-*.md")), "Tier-1 fan-out task must spawn"

    # --- Tony issues a reaffirm (no levels of his own -> inherits the SAME bridge's levels)
    (tmp_path / "v.json").write_text(json.dumps(
        [{"date": "2026-06-09", "symbol": "AAPL", "verdict": "reaffirm", "confidence": "high"}]))
    monkeypatch.setattr(ap, "VERDICTS_FILE", tmp_path / "v.json")
    monkeypatch.setattr(ap, "EXECUTED_LOG", tmp_path / "exec.json")
    monkeypatch.setattr(ap, "BRIDGE_DIR", bridge_dir)   # levels come from the real bridge file
    monkeypatch.setenv("TONY_MARKET_SESSION", "open")
    monkeypatch.setenv("TONY_BOOK_CACHE", str(tmp_path / "book.json"))

    class _E2EBroker(_CloseBroker):
        """Flat until the buy fills — a pre-held AAPL would (correctly) trip the
        no-pyramiding guard and skip the very order this test verifies."""
        def __init__(self):
            super().__init__()
            self.buys = []

        def buy(self, symbol, notional, target, stop, risk_pct=None):
            self.buys.append({"symbol": symbol, "target": target, "stop": stop})
            return {"qty": 50, "entry": 200.0}

        def account(self):
            if not self.buys:
                return {"equity": 1_000_000.0, "cash": 1.0, "last_equity": 1_000_000.0,
                        "open_positions": []}
            return {"equity": 1_000_000.0, "cash": 1.0, "last_equity": 1_000_000.0,
                    "open_positions": [{"symbol": "AAPL", "qty": 50, "avg_entry_price": 200.0,
                                        "current_price": 205.0, "unrealized_pl": 250.0,
                                        "unrealized_plpc": 0.025}]}

        def open_orders(self):
            if not self.buys:
                return []
            return [{"symbol": "AAPL", "side": "sell", "limit_price": 220.0, "stop_price": None},
                    {"symbol": "AAPL", "side": "sell", "limit_price": None, "stop_price": 190.0}]

    b = _E2EBroker()
    res = ap.sync(broker=b)
    assert res["status"] == "ok"
    # the order carries the bridge's protective levels — never a naked entry
    assert b.buys == [{"symbol": "AAPL", "target": 220.0, "stop": 190.0}]
    assert "2026-06-09:AAPL:open" in json.loads((tmp_path / "exec.json").read_text())

    # --- the book cache sync wrote feeds Tony's next brief: protected position visible
    cache = tb.read_book_cache()
    pos = {p["symbol"]: p for p in cache["positions"]}
    assert pos["AAPL"]["protected"] and pos["AAPL"]["stop"] == 190.0 and pos["AAPL"]["target"] == 220.0

    # --- and execution feedback closes the loop in Tony's own words
    monkeypatch.setenv("TONY_VERDICTS_FILE", str(tmp_path / "v.json"))
    monkeypatch.setenv("TONY_EXECUTED_LOG", str(tmp_path / "exec.json"))
    feedback = tb.execution_feedback_block()
    assert "AAPL (reaffirm) filled — in your book" in feedback
