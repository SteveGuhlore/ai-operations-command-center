# Design — Tony Telegram as the public-facing FACE (backend stays private)

**Date:** 2026-06-06 · **Status:** approved design (build in one pass).
Builds on `2026-06-06-tony-telegram-companion-design.md` and `2026-06-06-tony-telegram-face-roadmap.md`.

## Operator intent
Make Tony's Telegram bot the **entire front-facing face** of Tony Stocks — conversational, visual,
proactive, personable — while the **dashboard and API keys stay an internal, private backend the
operator never shares**. Telegram becomes a **shareable public channel** others can follow and talk to;
the existing whitelisted operator chat becomes a private "cockpit" tier. Public goes live this session
once tested. Read-only forever: chat NEVER places, cancels, or modifies a trade.

## Decisions (locked with the operator)
- **Topology:** Approach A — ONE bot, two tiers resolved by *sender*. Operator chat id → full private
  cockpit (unmetered, everything incl. watchlist). Everyone else → public read-only tier. Tony
  *broadcasts* to a public channel; strangers can also DM the bot for read-only commands + NL Q&A.
- **Public data-exposure policy:** PUBLIC may see symbols, win/loss, %, R-multiple, **dollar P/L,
  account equity, and position sizes** (it is a paper account; transparency is the pitch). The ONLY
  thing held back from public is the **watchlist / "what he's eyeing next"** (front-running + saved as
  members-discussion fodder for later). The private backend is keys, the dashboard, and bot/scanner
  internals — never trade data.
- **Public NL chat:** ON at launch but **rate-limited + global-daily-LLM-budget-capped**, with a
  canned-FAQ shortcut so common questions cost $0. Commands + button taps are always free (no LLM).
  Operator tier is unmetered.
- **Go-live:** flip public this session after tests pass + runner restart.
- **`/record`:** summary line + most-recent **12** closed trades as compact rows + a "Show 12 more"
  inline button that pages older trades. Everything stays in-chat (no external links → respects "no
  dashboard access").

## Architecture

### Tier model (the public/private split)
`tier_for(chat_id) -> "operator" | "public"`: operator iff `str(chat_id) == TELEGRAM_CHAT_ID`, else
public. Pure function. Every inbound update and every outbound proactive post is tier-aware.

### Cost containment (why public DMs do NOT mean an LLM call per message)
1. Commands (`/status /record /explain /glossary /help`) and inline-button taps are pure read-only
   fetches + `tony_voice` formatters — **zero LLM calls**. This is most interaction.
2. Only free-text messages can reach the LLM, and the public path gates them with: a per-user sliding-
   window rate limit, a global daily LLM cap (operator-set), and a canned-FAQ matcher tried first.
   Over budget/limit → a canned "tap a button / try a command" reply, no model call.

### Bug fixes (FIRST, before features)
- **Latency:** dedicated daemon thread doing real long-polling (`getUpdates timeout=25`) started once
  at runner boot; replaces the once-per-180s `timeout=0` poll. The cycle no longer drives polling.
- **Offset robustness:** advance the offset only past updates that were handled or *intentionally*
  skipped (public-off stranger, rate-limited, non-text). On a **transient send failure**, stop
  advancing at that update so it retries — no silently-lost replies.

### Modules
- **`runner/tools/telegram_policy.py` (new)** — `is_operator()`; public data-exposure policy
  (watchlist blocked for public); per-user + global-daily rate limiter persisted to
  `workspace/telegram-public-state.json` (fail-soft); canned-FAQ matcher (keyword → canned Tony answer).
- **`runner/tools/telegram_inbox.py` (rework)** — long-poll thread; `tier_for` routing;
  `callback_query` handling (button taps + paging); `allowed_updates=["message","callback_query"]`;
  public path runs policy + rate limiter before any LLM. Offset robustness as above.
- **`runner/tools/notify.py` (extend)** — optional `chat_id` override (reply to the DM sender, not the
  operator); `reply_markup` (inline buttons); `answer_callback_query` + `editMessageText` (paging);
  `broadcast()` → `TELEGRAM_PUBLIC_CHANNEL_ID` for proactive public posts. All fail-soft.
- **`runner/tools/tony_synthesis.py` (extend)** — `answer(question, context, *, public)`: NL reply as
  Tony from live read-only data (account/record/realized/thesis); facts pinned ("use only these");
  length-bounded; public variant strips watchlist; fail-soft → canned fallback.
- **`runner/tools/tony_voice.py` (extend)** — `/record` = summary + most-recent-12 compact rows
  (`🟥 FCX −$462 · Fri · stop`) + paging metadata; pure formatters, unit-tested.
- **`runner/tools/tony_nudges.py` (new)** — proactive: market-open game plan, stop-out heads-up
  ("I cut FCX — here's why"), new equity high, EOD sign-off; de-dup via state files; sent to public
  channel + operator.

### Data flow
Inbound: `TG → long-poll thread → per update: tier_for → route(command | callback | NL) →
[public: policy + rate-limit + FAQ] → read-only fetch → tony_voice format → notify(reply to sender)`;
offset advances on success/intentional-skip only.
Outbound proactive: `cycle/event → tony_nudges → broadcast(channel) + notify(operator)`, de-duped.

### Concurrency
The long-poll thread runs alongside the 180s cycle. Started once via a module guard. All fetches are
read-only; the only shared writes are per-purpose state files (offset, rate-limit, nudge de-dup), each
single-writer. Runner restart required after these `runner/**` edits (module caching).

## Safety / non-goals
- READ-ONLY everywhere; chat must NEVER place/cancel/modify a trade (hard non-goal, enforced by simply
  having no trade path in the inbox).
- Public never exposes keys, the dashboard, scanner/bot internals, or the watchlist.
- Touches NOTHING in the bot↔Tony contract.
- Behind opt-in flags: `TONY_PUBLIC=on`, `TELEGRAM_PUBLIC_CHANNEL_ID`, public NL caps; existing
  `TONY_NOTIFY`, `TONY_TELEGRAM_CHAT`, `TONY_SYNTH` unchanged. Fail-soft throughout.

## Build phases
- **Phase 0 (this pass):** bug fixes → tier resolver + policy + rate-limiter + FAQ → notify extensions
  → Tier 1a NL chat (operator + gated public) → Tier 1b inline buttons + callback paging → Tier 1c
  proactive nudges → `/record` per-trade + paging → tests green → runner restart → flip public.
- **Later (spec'd, not built now):** Tier 2 transparency commands (`/today`, `/watchlist`[operator],
  `/research`, `/learn`, `/thesis SYM`); Tier 3 charts via `sendPhoto`; Tier 4
  education/personality/milestones.

## Testing
Pure units + mocked httpx: `tier_for`, policy allow/deny, rate-limiter window+cap, FAQ matcher,
offset-stops-on-send-fail, `say_record` paging, callback paging, public-vs-operator routing, broadcast
targeting, nudge de-dup. Keep all 464 green + add new.

## Env (gitignored `.env`)
`TONY_PUBLIC=on` · `TELEGRAM_PUBLIC_CHANNEL_ID=...` · `TONY_PUBLIC_NL_PER_USER_HOUR=...` ·
`TONY_PUBLIC_NL_DAILY_CAP=...` (existing `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TONY_NOTIFY`,
`TONY_TELEGRAM_CHAT`, `TONY_SYNTH` reused).
