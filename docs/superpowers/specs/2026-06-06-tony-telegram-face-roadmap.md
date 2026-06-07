# Roadmap — Tony Telegram as "the face of the agent"

**Date:** 2026-06-06 · **Status:** roadmap (Phases 1–3 + ledger fix DONE; Tiers 1–4 below pending).
Builds on `2026-06-06-tony-telegram-companion-design.md`. Operator goal: make Tony the conversational,
visual, proactive, personable face of the trading agent — readable + informative so a beginner slowly
learns. First person always. Read-only (chat NEVER trades).

## Done (live on master)
- First-person plain+numbers alerts with thesis/reason/R (Phase 1).
- Two-way chat: `/status /record /explain /glossary /help`, whitelisted (Phase 2).
- LLM synthesis: daily wrap, weekly review, learning digest (Phase 3).
- **Realized ledger reconciled from Alpaca fills** so `/record` + recap are TRUE (captured Friday's
  4 stop-outs; killed the bogus record). This is the data foundation every feature below relies on.

## Tier 1 — talkable & proactive (highest impact, build next)
- **Natural-language chat:** non-command text → an LLM reply AS Tony, using live data + his tools
  (`tony_outcomes`, `get_stock_data`, account/record). Route in `telegram_inbox.reply_for` fallback to
  a new `tony_synthesis.answer(question, context)`; bound length; gate on `TONY_TELEGRAM_CHAT`.
- **Inline keyboard buttons:** Telegram `reply_markup` with 📊 Status / 📈 Record / 🔍 Explain so a
  non-typer taps. Handle `callback_query` in the poller (extend `allowed_updates`).
- **Proactive nudges (Tony texts first):** market-open game plan, a stop-out heads-up ("I cut FCX —
  here's why"), new equity high, end-of-day sign-off. Hook off existing events (`notify_exit`, equity
  snapshot) + a small daily scheduler; de-dup via state files.

## Tier 2 — show his work (transparency)
- `/today` (timeline of his actions from `done/` + realized), `/watchlist` (next-open candidates from
  `research-queue.json`), `/research` (what he studied off-hours), `/learn` (self-learning loop in
  plain words via `lessons_block`), `/thesis SYM` (full verdict reasoning, not the one-liner).

## Tier 3 — visual reporting (charts as images)
- Equity curve, position-P/L bars, win-rate trend rendered to PNG (matplotlib) and sent via Telegram
  `sendPhoto`; attach to the daily/weekly digest. New `tony_charts.py`; reuse `equity_history`.

## Tier 4 — education & personality (the "face")
- "Lesson of the day" tied to a real trade; inline glossary expansions; `/beginner` mode (strip
  numbers); consistent Tony persona (confident, humble after losses, curious); milestone celebrations.

## Cross-cutting / ops
- Long-message chunking; rate-limit friendliness; `callback_query` + `sendPhoto` support in the poller;
  per-feature opt-in flags; everything fail-soft + read-only; touch NOTHING in the bot↔Tony contract.

## Suggested build order
Tier 1 (NL chat → buttons → proactive) → Tier 3 charts → Tier 2 transparency commands → Tier 4 polish.
Each ships behind tests + a runner restart. Best tackled in focused sessions to keep diffs reviewable.
