# Design — Tony Telegram Companion ("Tony, in his own voice")

**Date:** 2026-06-06 · **Status:** approved (design), implementation in progress
**Goal:** turn the thin one-way Telegram feed into a first-person companion that a total beginner
understands and slowly learns from — great reporting, real synthesis, and two-way chat.

## Operator intent (verbatim)
- Readable **and** informative: the reader should see **what Tony did and why**, so they "eventually
  and slowly learn." → plain-English + the real numbers + a gentle teach-moment.
- **First person.** Tony is his own person — every message is "I", as Tony. You text Tony; Tony texts
  back as himself.
- Build **all phases** now.

## Audit — what exists today
One-way outbound only (`runner/tools/notify.py` → Telegram `sendMessage`, HTML). Live
(`TONY_NOTIFY=telegram`, token + chat_id in `.env`). Fail-soft, config-gated, touches nothing in the
bot↔Tony contract. Four messages fire: entry (`alpaca_paper._notify_entry_safe`), exit
(`_notify_closed`), reprice (`sync`), daily digest (`main._maybe_send_daily_summary`).
**Weaknesses:** pure jargon, no "why"/thesis, exit alert drops the reason+R-multiple it already
supports, daily digest is a flat metric dump, no inbound, no synthesis of what Tony is *learning*.

## Voice (shared by every surface)
First-person Tony. Each message = **a human sentence (what + why) → the real numbers → an optional
one-line teach-moment**. Confident, plain-spoken, never condescending. Example entry:
> 🟢 **I bought CARR.** I think it climbs from $30 toward $40. If it drops to $25 I'll sell
> automatically so a bad call only costs ~1% of the account.
> `120 sh · entry $30 · stop $25 · target $40`
> _Why: breakout over $29 resistance on heavy volume._

## Architecture (isolated, testable units)
- **`runner/tools/tony_voice.py` (new) — pure persona/formatting.** Functions take trade facts and
  return first-person strings: `say_entry`, `say_exit`, `say_reprice`, `say_daily`, plus small helpers
  (`teach(term)` glossary lines, plain money/price). No I/O — fully unit-testable. `notify.py`'s
  `notify_*` become thin wrappers that call these.
- **`runner/tools/telegram_inbox.py` (new) — inbound.** `poll_and_handle()` long-polls Telegram
  `getUpdates` with a persisted offset (`workspace/telegram-inbox-state.json`), **whitelisted to
  `TELEGRAM_CHAT_ID` only** (ignore everyone else — a bot token is semi-public), routes commands, and
  replies via `notify()`. Called once per `run_cycle` (cheap: one short GET when idle). Gated by
  `TONY_NOTIFY=telegram` + opt-in `TONY_TELEGRAM_CHAT=on` (default off) so polling never starts
  unexpectedly.
- **`runner/tools/tony_synthesis.py` (new) — LLM narratives.** `daily_wrap()`, `weekly_review()`,
  `learning_digest()` build a compact context (book, realized record, calibration, the self-learning
  files `learned_rules.md` / `pattern-library.md` / `discover_edges`) and ask the existing model client
  (`runner/agents/base.py`, gemini-2.5) to write a short first-person narrative, then `notify()` it.
  Scheduled from `main` (daily after close; weekly Fri close). Fail-soft; degrades to the Phase-1
  metric digest if the model call fails.

## Phases
**Phase 1 — Humanize the 4 alerts (no LLM).**
- Thread the verdict thesis into the entry alert: at `_notify_entry_safe`, look up the symbol's latest
  verdict (`VERDICTS_FILE`) and pass a one-line `reason`.
- Restore exit `reason` (`tony_realized.infer_reason`) + R-multiple (P/L ÷ risk$) into `notify_exit`.
- Rewrite all four through `tony_voice` in first person (mix of words + numbers + teach line).

**Phase 2 — Two-way chat (inbound).** Commands (whitelisted): `/status` (book + P/L in plain words),
`/record` ("I've been right on 6 of my last 9 calls — best at breakouts, worst at earnings"),
`/explain <SYM>` (why I hold it), `/glossary`, `/help`. Free-text → a cheap LLM reply as Tony
(optional, behind the same gate). Offset + dedup so a message is handled once.

**Phase 3 — Synthesis (LLM).** `daily_wrap` ("My day in 3 sentences"), `weekly_review` ("This week I
made $X across 7 trades, won 60%; my biggest lesson…"), `learning_digest` (surfaces the weekend
self-learning in human terms). First person, reads the loop files we already wired.

**Phase 4 — Polish.** Consistent Tony voice, mobile-friendly short lines, `/glossary`, optional
`/beginner` toggle that strips numbers for pure plain-English.

## Safety / non-goals
- **Read-only.** Chat NEVER places/cancels/modifies trades — it reports and explains. (A future
  approve-trades flow is explicitly out of scope here.)
- Whitelist inbound to `TELEGRAM_CHAT_ID`; ignore all other senders silently.
- Everything fail-soft and config-gated; must NEVER block or break the trading path, and touches
  nothing in the bot↔Tony file contract.

## Testing
- `tony_voice`: unit tests per message type (first person, contains the numbers, win vs loss vs stop
  phrasing, teach line present/bounded).
- `telegram_inbox`: offset advance, whitelist rejection, each command's reply (HTTP mocked), dedup.
- `tony_synthesis`: context assembly + fail-soft degrade (model mocked).
- Extend `tests/runner/test_notify.py`; new `test_telegram_inbox.py`, `test_tony_voice.py`,
  `test_tony_synthesis.py`. Keep the suite green.

## Ops
Runner restart after the edits (module caching). New env: `TONY_TELEGRAM_CHAT=on` to enable inbound.
