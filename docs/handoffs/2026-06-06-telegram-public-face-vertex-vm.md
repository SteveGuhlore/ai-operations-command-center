# Next-Session Handoff — Telegram public-face LIVE · Vertex cutover (propagation-blocked) · VM deploy ready

**Written:** 2026-06-06 (Sat) night ET. **For:** a fresh Command Center session.
**State:** everything below is committed AND pushed to `origin/master` (tip **`306f547`**). Runner restarted
and live locally on :8765. **484 tracked tests pass** (2 failures are a PRE-EXISTING untracked WIP file,
`tests/runner/test_tony_outcomes_symbol.py` + ` M runner/tools/tony_outcomes.py` — NOT ours).
Don't `git add -A` (huge untracked tree); stage explicit paths. Restart the runner after any `runner/**`
edit (module caching). **Operator preference: don't surface cost warnings — keep working.**

---

## 1. What shipped THIS session (master, newest first)
- `306f547` **feat(vertex): accept GOOGLE_CLOUD_PROJECT/LOCATION aliases** — base.py now reads BOTH the
  CC's `VERTEX_*` names and the google-genai SDK `GOOGLE_CLOUD_*` names the VM `.env` uses.
- `f73d838` **fix(research): inject REAL realized record into learning tasks** (the audit fix — §3).
- `c3c0084` **Merge: Telegram public-facing FACE** (the big feature — §2).
- Spec: `docs/superpowers/specs/2026-06-06-tony-telegram-public-face-design.md`.
  Plan: `docs/superpowers/plans/2026-06-06-tony-telegram-public-face.md`.

---

## 2. ⭐ Telegram = the public-facing FACE (LIVE, operator tier; public tier built, OFF)
Operator goal: make Tony's Telegram bot the entire front-facing face; dashboard + keys stay a private
backend. ONE bot, two tiers resolved by **sender chat id** (`runner/tools/telegram_policy.tier_for`):
- **operator** (= `TELEGRAM_CHAT_ID`, the chat the operator already uses): full private cockpit,
  unmetered, sees everything incl. watchlist.
- **public** (anyone else, gated by `TONY_PUBLIC=on`): READ-ONLY, rate-limited + daily-LLM-capped,
  watchlist BLOCKED (front-running guard). Tony broadcasts entries/exits to a public channel; strangers
  can DM the bot.

**Built + tested + live (operator tier works NOW):**
- **Bug fix 1 — latency:** dedicated long-poll daemon thread (`telegram_inbox.start_poller` →
  `getUpdates timeout=25`), started from `main._maybe_handle_telegram_chat`. Replies are now near-instant
  (was ~3-min cycle lag).
- **Bug fix 2 — offset robustness:** `poll_and_handle` advances the offset only past handled/intentionally-
  skipped updates; a transient send failure STOPS advancement so the reply retries (no lost replies).
- **Paged `/record`:** summary + most-recent **12** closed trades named with $P/L, %, when, why
  (`🟥 FCX −$462 · yesterday · hit my stop`) + **"Show 12 more ▶"** inline button paging
  (`tony_voice.say_record_page`, `tony_realized.records()`). Verified rendering Friday's 4 real stops.
- **Inline buttons + callbacks:** 📊 Status / 📈 Record / 📖 Glossary / ❓ Help; `callback_query` handled.
- **Public tier:** `telegram_policy` (tier_for, public command allowlist, canned-FAQ, per-user+global NL
  rate limiter persisted to `workspace/telegram-public-state.json`).
- **Natural-language chat:** `tony_synthesis.answer(question, public=...)` — grounded in live read-only
  facts, watchlist-safe, fail-soft → canned fallback.
- **Proactive nudges:** `tony_nudges.maybe_equity_high()` + `maybe_eod_signoff()` (de-duped via
  `workspace/nudge-state.json`), wired in the cycle; entries/exits now ALSO `broadcast()` publicly
  (added to `notify_entry`/`notify_exit`).
- **notify.py extensions:** `chat_id` override, `inline_keyboard`, `broadcast()` (→
  `TELEGRAM_PUBLIC_CHANNEL_ID`), `answer_callback_query`, `edit_message_text`.

**Cost containment (why public DMs ≠ an LLM call per message):** commands + button taps are pure
formatters ($0); only free-text hits the LLM, gated by per-user rate limit + global daily cap + canned
FAQ. Operator is unmetered.

**To GO PUBLIC (last step, operator-gated):** create a Telegram channel, add the bot as admin, then set
in `.env`: `TONY_PUBLIC=on`, `TELEGRAM_PUBLIC_CHANNEL_ID=<id>`, `TONY_PUBLIC_NL_PER_USER_HOUR=5`,
`TONY_PUBLIC_NL_DAILY_CAP=100`; restart the runner; verify a stranger account gets read-only replies,
`/watchlist` is refused, and entries/exits hit the channel. Operator wants this flipped once tested.

**Later phases (spec'd, NOT built):** Tier 2 transparency commands (`/today /watchlist`[operator]
`/research /learn /thesis SYM`); Tier 3 charts via `sendPhoto` (`tony_charts.py`, reuse `equity_history`);
Tier 4 education/personality/milestones. READ-ONLY forever — chat NEVER trades (hard non-goal).

---

## 3. ⭐ Audit fix — self-learning was learning from the WRONG track (LIVE)
**Operator caught:** the overnight research tasks (`workspace/tasks/done/TONY-RW-*-20260608.md`) reported
"1 closed at +1.05% profit, no losing trades" — but the REAL book lost **~$946 to 4 stop-outs** Friday
(FCX×2, SLB, SNAP). Root cause: two performance tracks — the thin **verdict track** (`tony_outcomes` /
`tony_stocks_record.json`, 1 sample, +1.05%) vs the **realized track** (`tony-realized.json`, the truth).
The learning tasks defaulted to the rosy verdict track and wrote a **false-positive lesson** into
`vault/agents/market_research_worker/learned_rules.md` (`prompts.py` injects that file into every verdict,
so it was biasing real decisions).

**Fix (`f73d838`):** `research_wave._augment_body()` now injects the REAL realized record
(`_realized_block()`) into `tony_self_review`/`tony_realized_postmortem`/`tony_regrade` task bodies as
ground truth with an explicit "do NOT draw conclusions from the verdict track" instruction; adds a
"<5 graded → insufficient data, write no positive lesson" guard to `tony_calibration_study`/
`tony_edge_mining`. The false vault lesson was **retracted** (vault is gitignored — edited in place).
Watch the NEXT overnight drain to confirm the learning tasks now cite the real $946/4-stop record.

---

## 4. Vertex AI cutover to the $300 credit (config DONE, blocked on Google propagation)
Moving all Gemini calls (Tony/Atlas/Clay/Telegram NL) onto a new GCP free-trial account.
- **New project:** `stocks-bot-agent` · **billing acct** `016CD9-F2A8C6-C3070C` ("My Billing Account",
  holds the $300 credit, project IS linked) · **key:** `C:/Users/alexa/.gcp/tony-vertex.json`
  (service account `stocks-vertex@stocks-bot-agent…`).
- **`.env` updated** (local): `VERTEX_PROJECT=stocks-bot-agent`, `VERTEX_LOCATION=us-central1`,
  `GOOGLE_APPLICATION_CREDENTIALS=C:/Users/alexa/.gcp/tony-vertex.json`. (Old project was
  `outreach-497418` via `.vertex-key.json` — that's where prior Gemini spend went; old key still at repo
  root, no longer referenced.)
- **Verified:** auth mints a token ✅, routing picks Vertex ✅ (`base.AgentBase._use_vertex`), API shows
  Enabled ✅, billing linked ✅. **STILL 403** "API has not been used… or disabled" → Google **propagation
  delay** on a brand-new project (can take 10–20+ min after enable + billing link). NOT a config problem.
- **NEXT SESSION — "finish the vertex cutover":** re-run the verify (below). When it prints `CALL OK`,
  restart the LOCAL runner so it runs on the credit. If still 403 after 30 min, the only thing unverifiable
  from here is the IAM role — confirm `stocks-vertex@…` has **Vertex AI User** at
  `console.cloud.google.com/iam-admin/iam?project=stocks-bot-agent`.
```bash
PYTHONIOENCODING=utf-8 python - <<'PY'
import os
os.environ.update(VERTEX_PROJECT="stocks-bot-agent", VERTEX_LOCATION="us-central1",
                  GOOGLE_APPLICATION_CREDENTIALS=r"C:/Users/alexa/.gcp/tony-vertex.json")
os.environ.pop("GOOGLE_AI_API_KEY", None)
from runner.agents.base import AgentBase
print(AgentBase("x","gemini-2.5-flash","Reply one word",[]).run({"task_id":"t","body":"Say OK"}).get("output"))
PY
```

---

## 5. VM deployment readiness (one Ubuntu e2-medium VM runs bot + CC; shared local bridge folder)
Handoff from the bot side. CC-side audit of their 6 points:
1. **Push to GitHub** — ✅ done (`origin/master` `306f547`). VM clones from
   `https://github.com/SteveGuhlore/ai-operations-command-center.git`.
2. **Vertex env on VM** — ✅ works after `306f547`. CC reads BOTH `VERTEX_*` and `GOOGLE_CLOUD_PROJECT/
   LOCATION` (+ `GOOGLE_APPLICATION_CREDENTIALS`). `GOOGLE_GENAI_USE_VERTEXAI=true` harmless/not required.
3. **Alpaca — HARD RULE** ⚠️ operator action: `/opt/command-center/.env` MUST hold a DIFFERENT Alpaca
   paper account than the bot. Nothing in code enforces it.
4. **Outcomes feed** — ✅ CC already reads `TONY_OUTCOMES_FILE` (`tony_scorecard.py`, `tony_outcomes.py`).
   Set `TONY_OUTCOMES_FILE=/opt/trading-bot/reports/tony_stocks_outcomes.json`.
5. **Start commands** — ✅ valid/unchanged: `dashboard.server:app` (FastAPI, `dashboard/server.py:60`)
   and `python -m runner.main` (`__main__` at `runner/main.py:910`). NOTE: the Telegram long-poll thread
   starts inside `runner.main`'s cycle, so the `cc-runner` unit owns Telegram; dashboard unit is separate.
6. **Morning-Prep brief (NEW, NOT built)** — bot writes `bridge/tony-stocks/morning-prep/<DATE>.md`
   (one-way, planned-only research). CC does NOT yet consume it. Future add: a small reader that ingests
   it as research-only morning context (dedupe on dated filename), mirroring `runner/bridge/tony_bridge.py`.
   Contract spec lives in the BOT repo `docs/CONTRACTS/morning-prep-bridge.md`. Keep one-way separation.

---

## 6. Open items / suggested next-session order
1. **Finish Vertex cutover** (§4) — verify + restart runner once propagation clears. (cheapest, highest value)
2. **Flip Telegram public** (§2) — once operator creates the channel + gives the id.
3. **Build morning-prep reader** (§5.6) — small, behind the one-way contract.
4. **Watch the next overnight drain** (§3) — confirm learning tasks now cite the real realized record.
5. Telegram Tier 2/3/4 (§2) — later, focused sessions.

## 7. Key files
- Telegram: `runner/tools/{telegram_inbox,telegram_policy,tony_voice,tony_synthesis,tony_nudges,notify}.py`;
  cycle wiring `runner/main.py` (`_maybe_handle_telegram_chat` → `start_poller`; nudges after weekly synth).
- Realized ledger: `runner/ledger/tony_realized.py` (`records()`, `summary`, `reconcile_from_fills`).
- Self-learning: `runner/bridge/research_wave.py` (`_augment_body`, `_realized_block`, `_WAVE_TASKS`,
  `_ROUNDS`). Vault: `vault/agents/market_research_worker/learned_rules.md`, `vault/tony-stocks/pattern-library.md`.
- LLM client / Vertex routing: `runner/agents/base.py` (`AgentBase.__init__`, `_vertex_token`).
- Tests: `tests/runner/test_{telegram_inbox,telegram_policy,tony_voice,tony_synthesis,tony_nudges,notify,
  research_wave,realized_reconcile}.py`.

**Bottom line:** Telegram is Tony's near-instant, honest-data, first-person face (operator live; public a
flag away). The self-learning loop now learns from the REAL ledger, not the rosy 1-sample track. Vertex is
fully wired to the $300 credit and just waiting on Google's propagation. GitHub is current for the VM clone.
