# Tony Telegram Public-Face Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Tony's Telegram bot into the public-facing FACE of Tony Stocks — fixing the two chat bugs, then adding operator/public tiering, rate-capped natural-language chat, inline buttons, paged `/record`, and proactive nudges — while the dashboard/keys stay a private backend and chat stays READ-ONLY.

**Architecture:** ONE bot. A pure `tier_for(chat_id)` splits every inbound update and proactive post into `operator` (full private cockpit, unmetered) vs `public` (read-only, rate-limited, watchlist-blocked). A dedicated long-poll daemon thread fixes latency; offset advances only past handled/intentionally-skipped updates. Public free-text is gated by a rate limiter + canned FAQ before any LLM call. Proactive nudges broadcast to a public channel + the operator.

**Tech Stack:** Python 3.x, httpx (Telegram Bot API), pytest + monkeypatch. Telegram HTML parse mode. Existing modules: `runner/tools/{notify,telegram_inbox,tony_voice,tony_synthesis}.py`, `runner/ledger/{tony_realized,alpaca_paper,equity_history}.py`, `runner/main.py`.

**Conventions to follow (from the codebase):**
- Fail-soft: network/parse errors are logged at INFO and return a no-op result; never raise into the cycle.
- Opt-in env flags. Pure formatters live in `tony_voice`; I/O lives in `notify`/`telegram_inbox`.
- Tests monkeypatch `httpx` on the module under test and capture outbound `json=` payloads.
- Stage explicit paths on commit (never `git add -A`).
- After ALL `runner/**` edits land: restart the runner (kill `scripts/launch.py` tree + :8765 child, relaunch detached) — module caching.

---

## Task 1: Expose per-trade realized rows

**Files:**
- Modify: `runner/ledger/tony_realized.py`
- Test: `tests/runner/test_realized_reconcile.py` (add to existing)

- [ ] **Step 1: Write the failing test**

```python
def test_records_returns_rows_newest_first(tmp_path, monkeypatch):
    from runner.ledger import tony_realized as tr
    f = tmp_path / "tony-realized.json"
    monkeypatch.setattr(tr, "REALIZED_FILE", f)
    import json
    f.write_text(json.dumps([
        {"symbol": "AAA", "realized_pl": 10, "reason": "target", "date": "2026-06-01"},
        {"symbol": "BBB", "realized_pl": -5, "reason": "stop", "date": "2026-06-05"},
    ]), encoding="utf-8")
    rows = tr.records()
    assert [r["symbol"] for r in rows] == ["BBB", "AAA"]   # newest first by date
    assert tr.records(newest_first=False)[0]["symbol"] == "AAA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runner/test_realized_reconcile.py::test_records_returns_rows_newest_first -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'records'`

- [ ] **Step 3: Implement `records()`** (add after `summary()` in `runner/ledger/tony_realized.py`)

```python
def records(newest_first: bool = True) -> list:
    """All realized rows ordered by date (then symbol). For the paged /record view."""
    rows = sorted(_load(), key=lambda r: (str(r.get("date", "")), str(r.get("symbol", ""))))
    return list(reversed(rows)) if newest_first else rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runner/test_realized_reconcile.py::test_records_returns_rows_newest_first -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add runner/ledger/tony_realized.py tests/runner/test_realized_reconcile.py
git commit -m "feat(realized): records() exposes per-trade rows newest-first for paged /record"
```

---

## Task 2: Paged `/record` formatter in tony_voice

The new `/record` leads with the summary, lists the most-recent 12 closed trades as compact rows, and signals whether older trades remain (for the "Show more" button). Pure formatter.

**Files:**
- Modify: `runner/tools/tony_voice.py`
- Test: `tests/runner/test_tony_voice.py` (add)

- [ ] **Step 1: Write the failing test**

```python
def test_record_row_and_page():
    from runner.tools import tony_voice as v
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
    # paging: 13 rows -> first page shows 12, has_more True
    many = [dict(rows[0], symbol=f"S{i}") for i in range(13)]
    p0 = v.say_record_page(many, realized, page=0, page_size=12)
    assert p0["has_more"] is True and p0["text"].count("\n") >= 12
    p1 = v.say_record_page(many, realized, page=1, page_size=12)
    assert "S12" in p1["text"] and p1["has_more"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runner/test_tony_voice.py::test_record_row_and_page -v`
Expected: FAIL — `_record_row` / `say_record_page` not defined

- [ ] **Step 3: Implement** (add to `runner/tools/tony_voice.py`, after `say_record`)

```python
_REASON_WORD = {"stop": "hit my stop", "target": "hit my target", "close": "I stepped aside",
                "unknown": "closed out"}


def _day_label(date_str: str) -> str:
    """Friendly short day for a YYYY-MM-DD: weekday for the last week, else MM-DD."""
    from datetime import date, datetime
    try:
        d = datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return str(date_str or "")
    delta = (date.today() - d).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if 0 < delta < 7:
        return d.strftime("%a")
    return d.strftime("%m-%d")


def _record_row(r: dict) -> str:
    pl = float(r.get("realized_pl", 0) or 0)
    emoji = "🟩" if pl >= 0 else "🟥"
    amt = f"+${_money(pl)}" if pl >= 0 else f"−${_money(abs(pl))}"
    pct = r.get("pct")
    pct_s = f" ({pct:+.1f}%)" if isinstance(pct, (int, float)) else ""
    why = _REASON_WORD.get(r.get("reason", "unknown"), "closed out")
    return f"{emoji} <b>{r.get('symbol', '?')}</b> {amt}{pct_s} · {_day_label(r.get('date'))} · {why}"


def _record_summary(realized: dict | None) -> str:
    r = (realized or {}).get("all_time", {}) if realized else {}
    if not r.get("count"):
        return "I haven't closed any trades yet — still early."
    wins, losses, pl = r.get("wins", 0), r.get("losses", 0), float(r.get("realized_pl", 0) or 0)
    verb = "made" if pl >= 0 else "lost"
    return (f"I've closed {r['count']} trades — {wins} winner(s), {losses} loser(s) — and "
            f"{verb} ${_money(abs(pl))} overall.")


def say_record_page(rows: list, realized: dict | None, page: int = 0, page_size: int = 12) -> dict:
    """Paged track record: {'text', 'has_more', 'page'}. Page 0 leads with the summary; every page
    lists up to page_size closed trades (newest first). Pure."""
    page = max(0, int(page))
    start = page * page_size
    chunk = rows[start:start + page_size]
    lines = []
    if page == 0:
        lines.append("📈 <b>My track record so far.</b>")
        lines.append(_record_summary(realized))
    else:
        lines.append(f"📈 <b>More closed trades</b> (page {page + 1})")
    lines.extend(_record_row(r) for r in chunk)
    if not chunk:
        lines.append("That's all of them.")
    return {"text": "\n".join(lines), "has_more": start + page_size < len(rows), "page": page}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runner/test_tony_voice.py::test_record_row_and_page -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add runner/tools/tony_voice.py tests/runner/test_tony_voice.py
git commit -m "feat(voice): paged /record — summary + recent-12 per-trade rows + has_more"
```

---

## Task 3: notify.py — chat override, inline buttons, broadcast, callback ack, edit

**Files:**
- Modify: `runner/tools/notify.py`
- Test: `tests/runner/test_notify.py` (add)

- [ ] **Step 1: Write the failing test**

```python
def test_notify_chat_override_and_markup(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    sent = _capture(monkeypatch)
    kb = nf.inline_keyboard([[("📊 Status", "cmd:status")]])
    assert nf.notify("hi", chat_id="555", reply_markup=kb)["sent"] is True
    assert sent["chat_id"] == "555"                       # override beats TELEGRAM_CHAT_ID
    assert sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "cmd:status"


def test_broadcast_targets_public_channel(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_PUBLIC_CHANNEL_ID", "-100777")
    sent = _capture(monkeypatch)
    assert nf.broadcast("public news")["sent"] is True
    assert sent["chat_id"] == "-100777"


def test_broadcast_noop_without_channel(monkeypatch):
    monkeypatch.setenv("TONY_NOTIFY", "telegram")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.delenv("TELEGRAM_PUBLIC_CHANNEL_ID", raising=False)
    assert nf.broadcast("x")["sent"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runner/test_notify.py -k "override or broadcast" -v`
Expected: FAIL — `inline_keyboard`/`broadcast` not defined

- [ ] **Step 3: Implement** (edit `runner/tools/notify.py`)

Replace `notify` + `_telegram` and add helpers:

```python
def inline_keyboard(rows: list) -> dict:
    """Build a Telegram inline keyboard. rows = [[(label, callback_data), ...], ...]."""
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for (t, d) in row] for row in rows]}


def notify(text: str, *, parse_mode: str = "HTML", chat_id: str | None = None,
           reply_markup: dict | None = None) -> dict:
    """Send a message on the configured channel. chat_id overrides TELEGRAM_CHAT_ID (reply to a
    specific sender). Returns {sent: bool, ...}; never raises."""
    ch = _channel()
    if ch in _OFF:
        return {"sent": False, "reason": "disabled"}
    if ch == "telegram":
        return _telegram(text, parse_mode, chat_id, reply_markup)
    return {"sent": False, "reason": f"unknown channel '{ch}'"}


def _telegram(text: str, parse_mode: str, chat_id: str | None = None,
              reply_markup: dict | None = None) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return {"sent": False, "reason": "telegram not configured"}
    payload = {"chat_id": chat, "text": text, "parse_mode": parse_mode,
               "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = httpx.post(_TG_URL.format(token=token), json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        return {"sent": True}
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("notify telegram failed: %s", exc)
        return {"sent": False, "reason": str(exc)}


def broadcast(text: str, *, parse_mode: str = "HTML", reply_markup: dict | None = None) -> dict:
    """Post to the PUBLIC channel (TELEGRAM_PUBLIC_CHANNEL_ID). No-op if unset. Fail-soft."""
    if _channel() in _OFF:
        return {"sent": False, "reason": "disabled"}
    channel = os.environ.get("TELEGRAM_PUBLIC_CHANNEL_ID")
    if not channel:
        return {"sent": False, "reason": "no_public_channel"}
    return _telegram(text, parse_mode, channel, reply_markup)


def answer_callback_query(callback_id: str) -> dict:
    """Acknowledge a button tap so Telegram stops the client spinner. Fail-soft."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or not callback_id:
        return {"sent": False}
    try:
        httpx.post("https://api.telegram.org/bot{}/answerCallbackQuery".format(token),
                   json={"callback_query_id": callback_id}, timeout=_TIMEOUT)
        return {"sent": True}
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("answerCallbackQuery failed: %s", exc)
        return {"sent": False}


def edit_message_text(chat_id: str, message_id: int, text: str, *, parse_mode: str = "HTML",
                      reply_markup: dict | None = None) -> dict:
    """Edit an existing message in place (for paging). Fail-soft."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"sent": False}
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text,
               "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = httpx.post("https://api.telegram.org/bot{}/editMessageText".format(token),
                       json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        return {"sent": True}
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("editMessageText failed: %s", exc)
        return {"sent": False}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runner/test_notify.py -v`
Expected: PASS (existing tests still green — signature change is backward compatible)

- [ ] **Step 5: Commit**

```bash
git add runner/tools/notify.py tests/runner/test_notify.py
git commit -m "feat(notify): chat override, inline keyboards, broadcast(), callback ack, edit"
```

---

## Task 4: telegram_policy.py — tier, public allowlist, rate limiter, FAQ

**Files:**
- Create: `runner/tools/telegram_policy.py`
- Test: `tests/runner/test_telegram_policy.py` (new)

- [ ] **Step 1: Write the failing test**

```python
import time
from runner.tools import telegram_policy as tp


def test_tier_and_operator(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    assert tp.tier_for("999") == "operator"
    assert tp.tier_for("123") == "public"
    assert tp.is_operator("999") and not tp.is_operator("123")


def test_public_command_allowlist():
    assert tp.command_allowed("status", "public")
    assert tp.command_allowed("record", "public")
    assert not tp.command_allowed("watchlist", "public")   # front-running guard
    assert tp.command_allowed("watchlist", "operator")     # operator sees everything


def test_faq_matches_known_question():
    assert "paper" in tp.faq_answer("is this real money?").lower()
    assert tp.faq_answer("what is your favorite color") is None


def test_rate_limiter_per_user_and_global(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "STATE_FILE", tmp_path / "telegram-public-state.json")
    monkeypatch.setenv("TONY_PUBLIC_NL_PER_USER_HOUR", "2")
    monkeypatch.setenv("TONY_PUBLIC_NL_DAILY_CAP", "3")
    now = time.time()
    assert tp.allow_nl("u1", now)        # 1
    assert tp.allow_nl("u1", now)        # 2
    assert not tp.allow_nl("u1", now)    # 3 -> per-user cap (2/hr) hit
    assert tp.allow_nl("u2", now)        # global 3rd allowed
    assert not tp.allow_nl("u2", now)    # global daily cap (3) hit
    # window rolls: an hour later u1 is allowed again (still under daily cap reset next day)
    assert tp.allow_nl("u1", now + 3601) is False  # daily cap still in force same day
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runner/test_telegram_policy.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `runner/tools/telegram_policy.py`**

```python
"""telegram_policy — public-tier guardrails for Tony's Telegram face.

Tony answers the operator (TELEGRAM_CHAT_ID) with everything, and the public with a read-only,
rate-limited, watchlist-free subset. Pure tier/allowlist logic + a small persisted rate-limit and a
canned-FAQ matcher so common questions never touch the LLM. Fail-soft: a bad state file degrades to
"allow nothing extra", never an exception into the cycle.
"""
import json
import logging
import os
import time
from pathlib import Path

_log = logging.getLogger(__name__)
STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "telegram-public-state.json"

# Commands the PUBLIC tier may run. Watchlist / "what he's eyeing next" is operator-only
# (front-running guard); everything that reports the realized past is public.
_PUBLIC_COMMANDS = {"start", "help", "status", "book", "record", "stats",
                    "explain", "why", "glossary", "terms"}

_FAQ = [
    (("real money", "real cash", "actual money", "really trading"),
     "It's a <b>paper account</b> — real prices, simulated money. So the trades and P/L are real "
     "decisions, but no actual cash is at stake. That's how I learn out loud without risking anyone."),
    (("what do you trade", "which stocks", "what stocks"),
     "US stocks — liquid names with clean setups. I post every entry and exit here with the why."),
    (("who are you", "what are you", "are you a bot", "are you ai"),
     "I'm Tony — an AI trader running a paper account. I think out loud and explain everything in "
     "plain English so you can follow along and learn."),
    (("advice", "should i buy", "should i sell", "tip"),
     "I can't give financial advice — I only narrate my own paper trades and reasoning. Always do "
     "your own homework before risking real money."),
]


def is_operator(chat_id) -> bool:
    return str(chat_id) == str(os.environ.get("TELEGRAM_CHAT_ID", ""))


def tier_for(chat_id) -> str:
    return "operator" if is_operator(chat_id) else "public"


def command_allowed(cmd: str, tier: str) -> bool:
    if tier == "operator":
        return True
    return (cmd or "").lower() in _PUBLIC_COMMANDS


def faq_answer(text: str) -> str | None:
    t = (text or "").lower()
    for keys, answer in _FAQ:
        if any(k in t for k in keys):
            return answer
    return None


def _load_state() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError as exc:
        _log.info("public state write failed: %s", exc)


def allow_nl(user_id, now: float | None = None) -> bool:
    """Consume one public NL allowance. False (no model call) when the per-user hourly window or the
    global daily cap is exceeded. Records the grant on success. Fail-soft."""
    now = time.time() if now is None else now
    per_user = int(os.environ.get("TONY_PUBLIC_NL_PER_USER_HOUR", "5"))
    daily_cap = int(os.environ.get("TONY_PUBLIC_NL_DAILY_CAP", "100"))
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    st = _load_state()
    if st.get("day") != day:
        st = {"day": day, "global": 0, "users": {}}
    users = st.setdefault("users", {})
    hits = [t for t in users.get(str(user_id), []) if now - t < 3600]
    if len(hits) >= per_user:
        users[str(user_id)] = hits
        _save_state(st)
        return False
    if int(st.get("global", 0)) >= daily_cap:
        return False
    hits.append(now)
    users[str(user_id)] = hits
    st["global"] = int(st.get("global", 0)) + 1
    _save_state(st)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runner/test_telegram_policy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add runner/tools/telegram_policy.py tests/runner/test_telegram_policy.py
git commit -m "feat(telegram): public-tier policy — tier_for, allowlist, FAQ, rate limiter"
```

---

## Task 5: tony_synthesis.answer() — natural-language reply as Tony

**Files:**
- Modify: `runner/tools/tony_synthesis.py`
- Test: `tests/runner/test_tony_synthesis.py` (add)

- [ ] **Step 1: Write the failing test**

```python
def test_answer_pins_facts_and_is_public_safe(monkeypatch):
    from runner.tools import tony_synthesis as ts
    captured = {}
    monkeypatch.setattr(ts, "_narrate", lambda prompt, max_words=90: captured.setdefault("p", prompt) or "Hey — I'm up nicely today.")
    out = ts.answer("how are you doing?", public=True)
    assert out == "Hey — I'm up nicely today."
    assert "use only these" in captured["p"].lower()
    assert "watchlist" not in captured["p"].lower()      # public answer never leaks the watchlist


def test_answer_degrades_when_model_fails(monkeypatch):
    from runner.tools import tony_synthesis as ts
    monkeypatch.setattr(ts, "_narrate", lambda *a, **k: "")
    assert ts.answer("anything", public=True) == ""       # caller falls back to canned
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runner/test_tony_synthesis.py -k answer -v`
Expected: FAIL — `answer` not defined

- [ ] **Step 3: Implement** (add to `runner/tools/tony_synthesis.py`)

```python
def answer(question: str, *, public: bool = True) -> str:
    """Tony's first-person reply to a free-text question, grounded in live read-only book facts.
    Facts are pinned so the model can't invent numbers; the public variant never includes the
    watchlist. '' on any failure so the caller can fall back to a canned reply."""
    f = _book_facts()
    acct = f["acct"]
    pos = acct.get("open_positions", []) or [] if acct.get("status") == "ok" else []
    allt = (f["realized"] or {}).get("all_time", {})
    facts = (
        "Facts about me right now (use only these, do not invent numbers):\n"
        f"- Account equity: {acct.get('equity', 'unknown')}\n"
        f"- Open positions: {len(pos)} ({', '.join(p.get('symbol', '?') for p in pos[:10]) or 'none'})\n"
        f"- All-time closed: {allt.get('count', 0)} trades, "
        f"{allt.get('wins', 0)} win / {allt.get('losses', 0)} loss, realized {allt.get('realized_pl', 0)}\n"
        f"- I trade a paper account (simulated money, real prices).\n"
        f"My friend asked: \"{(question or '').strip()[:300]}\"\n"
    )
    if public:
        facts += ("Answer in my voice. Do NOT reveal any upcoming watchlist or stocks I'm about to "
                  "buy. No financial advice. If asked for advice, gently decline.")
    else:
        facts += "Answer in my voice, candidly — this is my operator."
    return _narrate(facts, max_words=80)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runner/test_tony_synthesis.py -k answer -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add runner/tools/tony_synthesis.py tests/runner/test_tony_synthesis.py
git commit -m "feat(synthesis): answer() — grounded first-person NL reply, public-safe"
```

---

## Task 6: telegram_inbox rework — tiered routing, callbacks, paging, offset robustness

This is the core. `poll_and_handle` stays the unit-testable seam (a single fetch+handle pass); the long-poll thread (Task 7) just calls it in a loop. Key changes: route by tier; public path runs policy + rate limiter + FAQ before LLM; handle `callback_query` (status/record/explain buttons + record paging); advance offset only past handled/intentionally-skipped updates (stop at the first transient send failure).

**Files:**
- Modify: `runner/tools/telegram_inbox.py`
- Test: `tests/runner/test_telegram_inbox.py` (extend; keep existing tests green)

- [ ] **Step 1: Write the failing tests**

```python
def test_public_command_runs_when_public_on(monkeypatch):
    monkeypatch.setenv("TONY_PUBLIC", "on")
    monkeypatch.setattr(ti, "_status_reply", lambda: "STATUS_OK")
    sent, posted = {}, []
    updates = [{"update_id": 60, "message": {"chat": {"id": 111}, "from": {"id": 111}, "text": "/status"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    res = ti.poll_and_handle()
    assert res["handled"] == 1
    assert posted[-1]["chat_id"] == "111"           # replied to the stranger's own chat
    assert ti._read_offset() == 61


def test_public_off_ignores_stranger_but_advances(monkeypatch):
    monkeypatch.setenv("TONY_PUBLIC", "off")
    sent, posted = {}, []
    updates = [{"update_id": 70, "message": {"chat": {"id": 111}, "from": {"id": 111}, "text": "/status"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    assert ti.poll_and_handle()["handled"] == 0
    assert posted == [] and ti._read_offset() == 71


def test_public_nl_rate_limited_uses_canned(monkeypatch):
    monkeypatch.setenv("TONY_PUBLIC", "on")
    from runner.tools import telegram_policy as tp
    monkeypatch.setattr(tp, "allow_nl", lambda uid, now=None: False)   # over budget
    monkeypatch.setattr(tp, "faq_answer", lambda t: None)
    sent, posted = {}, []
    updates = [{"update_id": 80, "message": {"chat": {"id": 111}, "from": {"id": 111}, "text": "how are you feeling?"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    ti.poll_and_handle()
    assert "tap" in posted[-1]["text"].lower() or "command" in posted[-1]["text"].lower()


def test_offset_stops_on_send_failure(monkeypatch):
    sent, posted = {}, []
    updates = [{"update_id": 90, "message": {"chat": {"id": 999}, "from": {"id": 999}, "text": "/help"}},
               {"update_id": 91, "message": {"chat": {"id": 999}, "from": {"id": 999}, "text": "/help"}}]
    def _get(url, params=None, timeout=None):
        class _R:
            def raise_for_status(self): pass
            def json(self): return {"ok": True, "result": updates}
        return _R()
    monkeypatch.setattr(ti.httpx, "get", _get)
    calls = {"n": 0}
    def _flaky(*a, **k):                       # first send fails, would-be second never reached
        calls["n"] += 1
        return {"sent": False, "reason": "boom"} if calls["n"] == 1 else {"sent": True}
    monkeypatch.setattr(ti, "notify", _flaky)
    ti.poll_and_handle()
    assert ti._read_offset() == 90             # did NOT advance past the failed update 90


def test_callback_record_paging(monkeypatch):
    monkeypatch.setenv("TONY_PUBLIC", "on")
    edits = []
    monkeypatch.setattr(ti, "edit_message_text",
                        lambda chat_id, message_id, text, **k: edits.append((chat_id, text)) or {"sent": True})
    monkeypatch.setattr(ti, "answer_callback_query", lambda cid: {"sent": True})
    monkeypatch.setattr(ti, "_record_rows", lambda: [{"symbol": f"S{i}", "realized_pl": 1, "reason": "target", "date": "2026-06-05"} for i in range(20)])
    monkeypatch.setattr(ti, "_realized_summary_safe", lambda: {"all_time": {"count": 20, "wins": 20, "losses": 0, "realized_pl": 20, "by_reason": {}}})
    updates = [{"update_id": 95, "callback_query": {"id": "cb1", "data": "rec:1",
               "message": {"message_id": 7, "chat": {"id": 999}}, "from": {"id": 999}}}]
    def _get(url, params=None, timeout=None):
        class _R:
            def raise_for_status(self): pass
            def json(self): return {"ok": True, "result": updates}
        return _R()
    monkeypatch.setattr(ti.httpx, "get", _get)
    ti.poll_and_handle()
    assert edits and "S12" in edits[-1][1]      # page 1 shows the 13th+ rows
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/runner/test_telegram_inbox.py -v`
Expected: FAIL — new behaviors not implemented (some existing tests may also need the `from` field, which the new code reads; that's fine — they're being extended here)

- [ ] **Step 3: Rewrite `runner/tools/telegram_inbox.py`**

```python
"""telegram_inbox — inbound Telegram chat for Tony (the public-facing FACE).

Long-polls getUpdates with a persisted offset and routes each message by TIER:
  - operator (TELEGRAM_CHAT_ID): the full private cockpit, unmetered.
  - public (anyone else, when TONY_PUBLIC=on): read-only commands + buttons (free) and rate-limited,
    budget-capped natural-language Q&A (canned-FAQ first, then the LLM). Watchlist is operator-only.
READ-ONLY: chat reports and explains, it NEVER places, cancels, or modifies a trade. Fail-soft — a
network error, bad payload, or model failure is a no-op, never an exception into the cycle. The offset
advances only past updates we handled or intentionally skipped; a transient send failure stops
advancement so the reply is retried next poll.
"""
import json
import logging
import os
from pathlib import Path

import httpx

from runner.tools.notify import (notify, broadcast, inline_keyboard, answer_callback_query,
                                  edit_message_text, _channel)
from runner.tools import tony_voice as voice
from runner.tools import telegram_policy as policy

_log = logging.getLogger(__name__)
_API = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 35.0          # long-poll: must exceed the getUpdates server timeout below
_LONGPOLL = 25
_ON = {"on", "1", "true", "yes", "telegram"}
_RECORD_PAGE = 12
STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "telegram-inbox-state.json"

_MENU = inline_keyboard([[("📊 Status", "cmd:status"), ("📈 Record", "cmd:record")],
                         [("📖 Glossary", "cmd:glossary"), ("❓ Help", "cmd:help")]])


def _chat_enabled() -> bool:
    return _channel() == "telegram" and \
        os.environ.get("TONY_TELEGRAM_CHAT", "off").strip().lower() in _ON


def _public_enabled() -> bool:
    return os.environ.get("TONY_PUBLIC", "off").strip().lower() in _ON


def _read_offset() -> int:
    try:
        return int(json.loads(STATE_FILE.read_text(encoding="utf-8")).get("offset", 0))
    except (json.JSONDecodeError, OSError, FileNotFoundError, ValueError, TypeError):
        return 0


def _write_offset(offset: int) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"offset": offset}), encoding="utf-8")
    except OSError as exc:
        _log.info("telegram offset write failed: %s", exc)


# --- read-only data fetchers (formatting lives in tony_voice) ---------------------------------------

def _status_reply() -> str:
    from runner.ledger.alpaca_paper import account_record
    from runner.ledger.tony_realized import summary as realized_summary
    acct = account_record()
    if acct.get("status") != "ok":
        return "I can't read my book right this second — try me again in a minute."
    return voice.say_status(acct, realized_summary())


def _record_rows() -> list:
    from runner.ledger.tony_realized import records
    return records(newest_first=True)


def _realized_summary_safe() -> dict:
    from runner.ledger.tony_realized import summary as realized_summary
    try:
        return realized_summary()
    except Exception:
        return {}


def _record_reply(page: int = 0) -> dict:
    """Returns {'text', 'has_more', 'page'} for the paged /record view."""
    return voice.say_record_page(_record_rows(), _realized_summary_safe(), page=page, page_size=_RECORD_PAGE)


def _explain_reply(symbol: str) -> str:
    if not symbol:
        return voice.say_explain("", "", False)
    from runner.ledger.alpaca_paper import _verdict_thesis, account_record
    from runner.tools.tony_verdict import VERDICTS_FILE
    try:
        verdicts = json.loads(VERDICTS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        verdicts = []
    thesis = _verdict_thesis(verdicts, symbol)
    held = False
    try:
        acct = account_record()
        held = any((p.get("symbol") or "").upper() == symbol.upper()
                   for p in acct.get("open_positions", []) or [])
    except Exception:
        pass
    return voice.say_explain(symbol, thesis, held)


def _record_markup(page: int, has_more: bool) -> dict | None:
    buttons = []
    if page > 0:
        buttons.append(("◀ Newer", f"rec:{page - 1}"))
    if has_more:
        buttons.append((f"Show {_RECORD_PAGE} more ▶", f"rec:{page + 1}"))
    return inline_keyboard([buttons]) if buttons else None


# --- routing ---------------------------------------------------------------------------------------

def reply_for(text: str, tier: str = "operator", user_id: str = "") -> dict:
    """Route a text message to a reply payload {'text', 'reply_markup'?}. Read-only.
    Public tier: command allowlist (watchlist blocked) + FAQ + rate-limited NL fallback."""
    t = (text or "").strip()
    if not t:
        return {"text": voice.HELP, "reply_markup": _MENU}
    parts = t.split()
    is_cmd = t.startswith("/")
    cmd = parts[0].lower().lstrip("/").split("@")[0]
    arg = parts[1] if len(parts) > 1 else ""

    if is_cmd:
        if tier == "public" and not policy.command_allowed(cmd, "public"):
            return {"text": "That one's just for my operator — try <code>/status</code>, "
                            "<code>/record</code>, or <code>/explain SYM</code>.", "reply_markup": _MENU}
        if cmd in ("start", "help"):
            return {"text": voice.HELP, "reply_markup": _MENU}
        if cmd in ("status", "book"):
            return {"text": _status_reply(), "reply_markup": _MENU}
        if cmd in ("record", "stats"):
            page = _record_reply(0)
            return {"text": page["text"], "reply_markup": _record_markup(0, page["has_more"])}
        if cmd in ("explain", "why"):
            return {"text": _explain_reply(arg), "reply_markup": _MENU}
        if cmd in ("glossary", "terms"):
            return {"text": voice.GLOSSARY, "reply_markup": _MENU}
        return {"text": ("I didn't catch that — try <code>/help</code> and I'll show you what I can "
                         "answer."), "reply_markup": _MENU}

    # --- free-text (natural language) ---
    faq = policy.faq_answer(t)
    if faq:
        return {"text": faq, "reply_markup": _MENU}
    if tier == "public" and not policy.allow_nl(user_id):
        return {"text": "I'm chatting with a lot of people right now — tap a button below or try "
                        "<code>/status</code> and I'll answer instantly.", "reply_markup": _MENU}
    from runner.tools.tony_synthesis import answer, synth_enabled
    out = answer(t, public=(tier == "public")) if synth_enabled() else ""
    if not out:
        return {"text": "I'm best with <code>/status</code>, <code>/record</code>, or "
                        "<code>/explain SYM</code> — tap below.", "reply_markup": _MENU}
    return {"text": out, "reply_markup": _MENU}


def _handle_callback(cb: dict) -> bool:
    """Handle a button tap. Returns True if a reply was sent (or intentionally finished)."""
    data = cb.get("data") or ""
    msg = cb.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    mid = msg.get("message_id")
    tier = policy.tier_for(chat)
    if tier == "public" and not _public_enabled():
        answer_callback_query(cb.get("id"))
        return True
    answer_callback_query(cb.get("id"))
    if data.startswith("rec:"):
        try:
            page = int(data.split(":", 1)[1])
        except ValueError:
            page = 0
        pg = _record_reply(page)
        res = edit_message_text(chat, mid, pg["text"], reply_markup=_record_markup(page, pg["has_more"]))
        return bool(res.get("sent"))
    if data.startswith("cmd:"):
        rep = reply_for("/" + data.split(":", 1)[1], tier, user_id=str((cb.get("from") or {}).get("id", "")))
        res = notify(rep["text"], chat_id=chat, reply_markup=rep.get("reply_markup"))
        return bool(res.get("sent"))
    return True


def poll_and_handle() -> dict:
    """One fetch+handle pass. Replies to the operator always (when chat on) and to the public when
    TONY_PUBLIC=on. Advances the offset only past handled/intentionally-skipped updates; a transient
    send failure stops advancement so the reply retries. Fail-soft no-op when disabled."""
    if not _chat_enabled():
        return {"handled": 0, "reason": "disabled"}
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    op_chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not op_chat:
        return {"handled": 0, "reason": "not_configured"}

    offset = _read_offset()
    try:
        r = httpx.get(
            _API.format(token=token, method="getUpdates"),
            params={"offset": offset, "timeout": _LONGPOLL,
                    "allowed_updates": json.dumps(["message", "callback_query"])},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        updates = r.json().get("result", []) or []
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("telegram getUpdates failed: %s", exc)
        return {"handled": 0, "reason": "fetch_failed"}

    handled = 0
    advance_to = offset - 1
    for u in sorted(updates, key=lambda x: int(x.get("update_id", 0))):
        uid = int(u.get("update_id", advance_to))
        ok, did_reply = _handle_update(u)
        if not ok:
            break                      # transient send failure: stop, retry this update next poll
        advance_to = uid
        handled += did_reply
    if advance_to >= offset:
        _write_offset(advance_to + 1)
    return {"handled": handled}


def _handle_update(u: dict) -> tuple[bool, int]:
    """Process one update. Returns (advance_ok, replied_count). advance_ok=False only on a transient
    send failure (so we retry); an intentionally-ignored update returns (True, 0)."""
    if "callback_query" in u:
        try:
            sent = _handle_callback(u["callback_query"])
            return (bool(sent), 1 if sent else 0)
        except Exception as exc:
            _log.info("telegram callback failed: %s", exc)
            return (True, 0)           # don't get wedged on a bad callback
    msg = u.get("message") or {}
    chat = str((msg.get("chat") or {}).get("id", ""))
    user_id = str((msg.get("from") or {}).get("id", chat))
    text = msg.get("text", "")
    if not text:
        return (True, 0)               # non-text: skip, advance
    tier = policy.tier_for(chat)
    if tier == "public" and not _public_enabled():
        return (True, 0)               # public off: ignore strangers, still advance
    try:
        rep = reply_for(text, tier, user_id)
        res = notify(rep["text"], chat_id=chat, reply_markup=rep.get("reply_markup"))
        if not res.get("sent"):
            return (False, 0)          # transient send failure: stop advancing
        return (True, 1)
    except Exception as exc:
        _log.info("telegram reply failed: %s", exc)
        return (True, 0)               # logic error on this message: skip it, keep going
```

NOTE: existing tests `test_handles_operator_and_dedups` / `test_whitelist_ignores_other_chats_but_advances_offset` use `reply_for(...)` returning a string and `notify` patched via `nf.httpx.post`. They must be updated: `reply_for` now returns a dict, and the inbox imports `notify` by name (patch `ti.notify`). Update those two tests to the new shape (operator help reply still contains "I'm Tony"; offset still advances to id+1).

- [ ] **Step 4: Update the two existing inbox tests to the new contract**

```python
def test_whitelist_ignores_other_chats_but_advances_offset(monkeypatch):
    monkeypatch.setenv("TONY_PUBLIC", "off")
    sent, posted = {}, []
    updates = [{"update_id": 41, "message": {"chat": {"id": 111}, "from": {"id": 111}, "text": "/status"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    res = ti.poll_and_handle()
    assert res["handled"] == 0 and posted == [] and ti._read_offset() == 42


def test_handles_operator_and_dedups(monkeypatch):
    sent, posted = {}, []
    updates = [{"update_id": 50, "message": {"chat": {"id": 999}, "from": {"id": 999}, "text": "/help"}}]
    _mock_updates(monkeypatch, updates, sent, posted)
    res = ti.poll_and_handle()
    assert res["handled"] == 1 and "I'm Tony" in posted[0]["text"] and ti._read_offset() == 51
```

(`_mock_updates` already patches `nf.httpx.post`; since `ti` imported `notify` by name, also `monkeypatch.setattr(ti, "notify", nf.notify)` is unnecessary — `ti.notify` *is* `nf.notify`, and `nf.httpx.post` is patched, so payloads still land in `posted`.)

- [ ] **Step 5: Run the full inbox + notify + voice suite**

Run: `python -m pytest tests/runner/test_telegram_inbox.py tests/runner/test_notify.py tests/runner/test_tony_voice.py tests/runner/test_telegram_policy.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add runner/tools/telegram_inbox.py tests/runner/test_telegram_inbox.py
git commit -m "feat(telegram): tiered routing, buttons+callbacks, paged /record, offset robustness"
```

---

## Task 7: Long-poll daemon thread + runner boot wiring

Replace the once-per-cycle poll with a dedicated daemon thread that calls `poll_and_handle()` in a loop (real long-polling: each call blocks up to ~25s server-side, so replies are near-instant). Started once at runner boot; idempotent.

**Files:**
- Modify: `runner/tools/telegram_inbox.py` (add `start_poller`)
- Modify: `runner/main.py` (start the thread at boot; drop the per-cycle poll)
- Test: `tests/runner/test_telegram_inbox.py` (add)

- [ ] **Step 1: Write the failing test**

```python
def test_start_poller_is_idempotent(monkeypatch):
    monkeypatch.setattr(ti, "_chat_enabled", lambda: True)
    monkeypatch.setattr(ti, "_poll_loop", lambda: None)   # don't actually loop
    ti._POLLER_STARTED = False
    t1 = ti.start_poller()
    t2 = ti.start_poller()
    assert t1 is not None and t2 is t1                     # only one thread ever starts
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runner/test_telegram_inbox.py::test_start_poller_is_idempotent -v`
Expected: FAIL — `start_poller` not defined

- [ ] **Step 3: Implement** (add to `runner/tools/telegram_inbox.py`)

```python
import threading
import time as _time

_POLLER_STARTED = False
_POLLER_THREAD = None
_poller_lock = threading.Lock()


def _poll_loop() -> None:
    while True:
        try:
            poll_and_handle()          # blocks up to ~_LONGPOLL via server-side long-poll
        except Exception as exc:       # belt-and-suspenders: the loop must never die
            _log.info("telegram poll loop error: %s", exc)
            _time.sleep(5)


def start_poller():
    """Start the single background long-poll thread (idempotent). No-op when chat is disabled."""
    global _POLLER_STARTED, _POLLER_THREAD
    with _poller_lock:
        if _POLLER_STARTED:
            return _POLLER_THREAD
        if not _chat_enabled():
            return None
        _POLLER_THREAD = threading.Thread(target=_poll_loop, name="tony-telegram-poll", daemon=True)
        _POLLER_THREAD.start()
        _POLLER_STARTED = True
        return _POLLER_THREAD
```

- [ ] **Step 4: Wire into runner boot, drop the per-cycle poll** (`runner/main.py`)

Replace the body of `_maybe_handle_telegram_chat` so the cycle just ensures the thread is up (cheap, idempotent) instead of doing a blocking poll itself:

```python
def _maybe_handle_telegram_chat() -> None:
    """Ensure the background Telegram long-poll thread is running (idempotent, fail-soft).
    Real-time replies happen on that thread, not in the cycle."""
    try:
        from runner.tools.telegram_inbox import start_poller
        start_poller()
    except Exception as exc:
        log.info("telegram poller start failed: %s", exc)
```

(Leave the call site at the top of `run_cycle` as-is — it now just keeps the thread alive.)

- [ ] **Step 5: Run test + the inbox suite**

Run: `python -m pytest tests/runner/test_telegram_inbox.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add runner/tools/telegram_inbox.py runner/main.py tests/runner/test_telegram_inbox.py
git commit -m "feat(telegram): dedicated long-poll daemon thread — near-instant replies (latency fix)"
```

---

## Task 8: Proactive nudges (Tony texts first) → public channel + operator

**Files:**
- Create: `runner/tools/tony_nudges.py`
- Test: `tests/runner/test_tony_nudges.py` (new)
- Modify: `runner/main.py` (call the equity-high + EOD checks in the cycle); `runner/ledger/alpaca_paper.py` `_notify_closed` (stop-out heads-up rides the existing exit event — verify it already broadcasts; if not, add a `broadcast` alongside the operator `notify`).

- [ ] **Step 1: Write the failing test**

```python
from runner.tools import tony_nudges as nudges


def test_equity_high_fires_once_per_high(tmp_path, monkeypatch):
    monkeypatch.setattr(nudges, "STATE_FILE", tmp_path / "nudge-state.json")
    posts = []
    monkeypatch.setattr(nudges, "broadcast", lambda text, **k: posts.append(text) or {"sent": True})
    monkeypatch.setattr(nudges, "notify", lambda text, **k: {"sent": True})
    monkeypatch.setattr(nudges, "_tony_equity", lambda: 1_010_000.0)
    monkeypatch.setattr(nudges, "_prev_peak", lambda: 1_000_000.0)
    assert nudges.maybe_equity_high()["sent"] is True
    assert "high" in posts[-1].lower()
    # second call at the same equity: de-duped, no new post
    monkeypatch.setattr(nudges, "_prev_peak", lambda: 1_010_000.0)
    assert nudges.maybe_equity_high()["sent"] is False


def test_eod_signoff_once_per_day(tmp_path, monkeypatch):
    monkeypatch.setattr(nudges, "STATE_FILE", tmp_path / "nudge-state.json")
    posts = []
    monkeypatch.setattr(nudges, "broadcast", lambda text, **k: posts.append(text) or {"sent": True})
    monkeypatch.setattr(nudges, "notify", lambda text, **k: {"sent": True})
    monkeypatch.setattr(nudges, "_daily_wrap_text", lambda: "Good day — up $1,200.")
    assert nudges.maybe_eod_signoff("2026-06-08")["sent"] is True
    assert nudges.maybe_eod_signoff("2026-06-08")["sent"] is False   # already signed off today
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runner/test_tony_nudges.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `runner/tools/tony_nudges.py`**

```python
"""tony_nudges — Tony texts first. Proactive, de-duped, public-safe notes to the channel + operator:
a new equity high and an end-of-day sign-off. Entry/exit heads-ups already ride notify_entry/exit.
Read-only and fail-soft; gated by TONY_PUBLIC (broadcast) + TONY_NOTIFY (operator). De-dup via a small
state file so a note fires at most once per event/day."""
import json
import logging
import os
from pathlib import Path

from runner.tools.notify import notify, broadcast

_log = logging.getLogger(__name__)
STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "nudge-state.json"


def _load() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def _save(d: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(d), encoding="utf-8")
    except OSError as exc:
        _log.info("nudge state write failed: %s", exc)


def _tony_equity():
    from runner.ledger.alpaca_paper import account_record
    acct = account_record()
    eq = acct.get("equity") if acct.get("status") == "ok" else None
    try:
        return float(eq) if eq is not None else None
    except (TypeError, ValueError):
        return None


def _prev_peak():
    return _load().get("equity_peak")


def _daily_wrap_text() -> str:
    from runner.tools.tony_synthesis import daily_wrap, synth_enabled
    if synth_enabled():
        txt = daily_wrap()
        if txt:
            return txt
    from runner.ledger.alpaca_paper import account_record
    from runner.tools.tony_voice import say_daily_header
    acct = account_record()
    return say_daily_header(acct.get("equity") if acct.get("status") == "ok" else None)


def _send_both(text: str) -> dict:
    b = broadcast(text)
    notify(text)                       # operator copy (own chat)
    return {"sent": bool(b.get("sent"))}


def maybe_equity_high() -> dict:
    """Fire once when Tony's equity sets a new high-water mark."""
    eq = _tony_equity()
    if eq is None:
        return {"sent": False, "reason": "no_equity"}
    peak = _prev_peak()
    try:
        peak_f = float(peak) if peak is not None else None
    except (TypeError, ValueError):
        peak_f = None
    if peak_f is not None and eq <= peak_f:
        return {"sent": False, "reason": "no_new_high"}
    st = _load()
    st["equity_peak"] = eq
    _save(st)
    if peak_f is None:                 # first observation: record the mark, don't shout
        return {"sent": False, "reason": "first_mark"}
    return _send_both(f"🚀 <b>New high.</b> My account just set a fresh record at "
                      f"${eq:,.0f}. Onward — I'll keep risking small and letting winners run.")


def maybe_eod_signoff(day: str) -> dict:
    """Fire once per market day: a plain-English wrap to the channel + operator."""
    st = _load()
    if st.get("eod_day") == day:
        return {"sent": False, "reason": "already"}
    text = _daily_wrap_text()
    if not text:
        return {"sent": False, "reason": "no_text"}
    st["eod_day"] = day
    _save(st)
    return _send_both("🌙 <b>That's a wrap on my day.</b>\n" + text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runner/test_tony_nudges.py -v`
Expected: PASS

- [ ] **Step 5: Wire into the cycle** (`runner/main.py`)

In `run_cycle`, after the existing `_maybe_send_daily_summary()` / `_maybe_send_weekly_synthesis()` block, add an equity-high check each cycle and an EOD sign-off when the market just closed. Use the existing `_is_market_closed()` helper and `datetime.date.today()`:

```python
    try:
        from runner.tools import tony_nudges
        tony_nudges.maybe_equity_high()
        if _is_market_closed():
            from datetime import date
            tony_nudges.maybe_eod_signoff(str(date.today()))
    except Exception as exc:
        log.info("nudges failed: %s", exc)
```

- [ ] **Step 6: Make exit heads-ups public** (`runner/ledger/alpaca_paper.py`)

Find where `_notify_closed` calls `notify_exit(...)`. Add a public broadcast of the same first-person line so a stop-out/target shows on the channel too. At the top of the file's imports add `from runner.tools.notify import broadcast` if absent, and right after the `notify_exit(...)` call add:

```python
            try:
                from runner.tools.tony_voice import say_exit
                broadcast(say_exit(symbol, qty, exit_price, pnl, reason, r_mult))
            except Exception as exc:
                _log.info("public exit broadcast failed: %s", exc)
```

(Use the exact local variable names present at that call site; if `r_mult` isn't in scope there, pass the same value `_notify_closed` passes to `notify_exit`.) Mirror the same one-line broadcast after the `notify_entry(...)` call so entries post publicly too.

- [ ] **Step 7: Run the nudges + ledger suites**

Run: `python -m pytest tests/runner/test_tony_nudges.py tests/runner/test_alpaca_paper.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add runner/tools/tony_nudges.py runner/main.py runner/ledger/alpaca_paper.py tests/runner/test_tony_nudges.py
git commit -m "feat(telegram): proactive nudges — new-high + EOD sign-off, public entry/exit broadcast"
```

---

## Task 9: Full suite + manual smoke + runner restart + go public

- [ ] **Step 1: Full test suite green**

Run: `python -m pytest tests/runner/ -q`
Expected: all previously-green tests + the new ones PASS (≥ 464 + new). Fix any regression before continuing.

- [ ] **Step 2: Manual render smoke (no network)**

Run (Windows console needs UTF-8):
```bash
PYTHONIOENCODING=utf-8 python -X utf8 -c "from runner.tools import telegram_inbox as t; print(t.reply_for('/record','operator','999')['text'])"
PYTHONIOENCODING=utf-8 python -X utf8 -c "from runner.tools import telegram_inbox as t; print(t.reply_for('/status','public','111')['text'])"
```
Expected: `/record` shows the summary + per-trade rows; `/status` renders.

- [ ] **Step 3: Set env flags** (`.env`, gitignored — do NOT commit)

```
TONY_PUBLIC=on
TELEGRAM_PUBLIC_CHANNEL_ID=<the public channel/group id the bot can post to>
TONY_PUBLIC_NL_PER_USER_HOUR=5
TONY_PUBLIC_NL_DAILY_CAP=100
```
(Existing `TONY_NOTIFY=telegram`, `TONY_TELEGRAM_CHAT=on`, `TONY_SYNTH=on`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` stay.)

- [ ] **Step 4: Restart the runner** (REQUIRED — `runner/**` changed; module caching)

```powershell
# kill the launcher tree + the :8765 child, then:
$root="C:\Users\alexa\Downloads\AI Operations Command Center"
$ts=Get-Date -Format "yyyyMMdd-HHmmss"
Start-Process python -ArgumentList "scripts/launch.py","--interval","180" -WorkingDirectory $root `
  -RedirectStandardOutput "$root\workspace\logs\launch-$ts.out.log" `
  -RedirectStandardError  "$root\workspace\logs\launch-$ts.err.log" -WindowStyle Hidden
```

- [ ] **Step 5: Live verification**
  - From the operator chat: `/record` shows the paged record; tap "Show 12 more" → it pages in place; tap a menu button → instant reply.
  - From a *non-operator* account: `/status` and `/record` work (public), `/watchlist` is refused, a free-text question gets a grounded reply, and spamming free-text hits the rate-limit canned reply.
  - Confirm an entry/exit also appears on the public channel.
  - Confirm reply latency is now seconds, not minutes.

- [ ] **Step 6: Final docs + handoff**

Update `docs/handoffs/` with a new dated handoff (what shipped, the flags, the go-public state, and the remaining Tier 2/3/4 phases). Commit:

```bash
git add docs/handoffs/<new-handoff>.md
git commit -m "docs(handoff): Tony Telegram public face LIVE (tiers, buttons, paged /record, nudges)"
```

---

## Self-review notes (coverage vs spec)
- Bug fix #1 latency → Task 7 (long-poll thread). Bug fix #2 offset robustness → Task 6 (`poll_and_handle` advance-on-success).
- Tier model → Task 4 (`tier_for`, allowlist). Cost containment → Tasks 4 (FAQ + rate limiter) + 6 (NL gated behind both).
- Tier 1a NL chat → Tasks 5 + 6. Tier 1b buttons + callback paging → Tasks 3 + 6. Tier 1c proactive nudges → Task 8.
- Paged `/record` per-trade → Tasks 1 + 2 + 6. Public/private data policy (watchlist blocked) → Task 4 + 6.
- Broadcast channel → Task 3 (`broadcast`) + Task 8. Go-live → Task 9.
- Later phases (Tier 2 commands, Tier 3 charts, Tier 4 polish) are intentionally out of scope for this plan.
```

