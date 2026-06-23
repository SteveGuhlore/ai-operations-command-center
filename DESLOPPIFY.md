# DESLOPPIFY — Cleanup Backlog

> Whole-repo code-quality scan of the AI Operations Command Center, generated 2026-06-23.
> Source: 5 parallel deep-dive audits (runner core, tools/integrations, Tony/ledger, dashboard/scripts, config/tests/hygiene).
> This file is the **backlog of record**. Work happens on dev branch `claude/eager-curie-tfw2zc`.

## How to use this
Pick a task by ID. Each item lists **Location · Why it matters · Recommendation · Fix-safety**. After each task is done, the status table is re-displayed for the next pick.

## Deploy safety (non-negotiable)
Production runs 24/7 on the VM (`/opt/command-center`, systemd `cc-runner`) off `master`, and it spends real LLM money + does live paper-trading. Therefore:
- All work lands on the **dev branch**, never straight to `master`/VM.
- Promotion to prod = the gated ritual only: staging soak (`scripts/setup_staging.sh`) → `scripts/promote_staging.sh` (full suite + readiness) → **after 4 PM ET** → VM fast-forward + `cc-runner` restart + readiness sweep.

## Legend
**Fix-safety:** 🟢 Safe now (additive/low-risk; lands + tests on dev) · 🟡 Stage (implement on dev, must soak before prod) · 🔴 Blocked (needs an operator decision first)
**Status:** ☐ todo · ◐ in progress · ✅ done (on dev) · 🚦 done-on-dev, awaiting staged promotion · ⏸ blocked

## Execution waves
- **Wave 0 — Baseline.** Capture green/red test baseline before any change (in progress).
- **Wave 1 — Critical, safe-now:** C1 C2 C3 C4 C5 C6 C7 (+ M32). Each with a regression test.
- **Wave 2 — Repo hygiene, zero/low-risk:** M38 N4 M22 N2 N3 M20 M21 M18 M19 N5 M25 M30 N1.
- **Wave 3 — Dedup & consistency, safe-now:** M1–M17, M23 M24 M26 M27 M28 M29 M31 N6.
- **Wave 4 — Structural, stage-it:** C8 C9 M33 M34 M35 M36 M37 N7.

---

# 1. CRITICAL

### C1 — Budget ledger resets on UTC date, not the ET trading day  🟢
- **Location:** `runner/ledger/budget.py:27-30` (cf. the already-fixed `runner/scheduler/daily_jobs.py:10-15`)
- **Why:** `_load_spend()` discards the ledger when `data["date"] != str(date.today())`. On the UTC VM that flips at ~8 PM ET, so the daily cap **and every per-role/per-pod cap reset to $0 mid-evening** — re-opening a second full budget of real LLM spend and re-enabling overnight spawns. This is the exact tz bug the scheduler already fixed for itself.
- **Recommendation:** Key rollover on `market_clock.trading_day()` (or explicit ET date), matching the scheduler.
- **Fix-safety:** 🟢 one-line source swap; add a test that freezes time to 00:30 UTC and asserts the ledger is NOT reset.

### C2 — `web_fetch` has no SSRF protection  🟢
- **Location:** `runner/tools/web.py:618-680` (guard at 621-628; ScrapingBee 631-648; direct fetch 657, `follow_redirects=True`)
- **Why:** Agent-controlled `url`, gated only by a substring blocklist of 6 social domains. Nothing blocks `http://169.254.169.254/…` (cloud metadata/creds), `localhost`, RFC-1918, or `file://`; a public URL can 302 into the metadata endpoint. On a 24/7 VM this is a path to cloud credentials. Runs on the **live trading path** (Tony fetches catalysts).
- **Recommendation:** Allow only http/https; resolve host and reject loopback/link-local/private/reserved IPs; re-validate after each redirect (or disable redirects) — for both direct and ScrapingBee paths.
- **Fix-safety:** 🟢 additive validation; test with metadata/loopback/private URLs.

### C3 — `web_research` output bypasses the injection sanitizer on the trading path  🟢
- **Location:** sanitizer applied only at `runner/tools/stock_news.py:125-130`; NOT on `runner/tools/web.py` output; consumed for trade decisions at `runner/bridge/tony_bridge.py:286,380,487,494` and `runner/bridge/research_wave.py:104,112,129`
- **Why:** `external_data_guard`'s own docstring names the risk — a poisoned web blob embeds a fake price/level directive Tony folds into his verdict, propagating a fraudulent level to the order layer. The guard is wired into the *news* feed but not the *web_research* feed Tony is told to call before writing target/stop.
- **Recommendation:** Run `web_research` search/fetch content (and `_extract_business_contact_info` raw text) through `sanitize_research()` before returning, mirroring `stock_news.py`.
- **Fix-safety:** 🟢 sanitizer is pure/deterministic; add a test feeding an injection string.

### C4 — Stored XSS across the dashboard  🟢
- **Location:** `dashboard/index.html` ~28 `innerHTML` sinks (e.g. 1179, 1374-1403, 1499-1511, 1632-1633, 1782+); `esc()` defined at 1988 but used only at 2024-2025; server note filter `dashboard/server.py:360-363`
- **Why:** CRM business names come from agent web-scraping and notes are free text; a stored `<img src=x onerror=…>` executes JS in the authenticated operator session — which can drive the POST endpoints that trigger pods, publish Stripe links, and log revenue. The server note filter blocks `|`/newlines but not `< > "`.
- **Recommendation:** Wrap every interpolated server value in `esc()` (or switch to `textContent`/DOM construction); harden `update_outreach_status` to reject/encode `< > "` (**M32**).
- **Fix-safety:** 🟢 client-side escaping + server filter; no behavior change.

### C5 — `runner/config.py` loads YAML with zero validation  🟢
- **Location:** `runner/config.py:7-32`
- **Why:** Every config is `yaml.safe_load`'d and returned raw — no schema, no required-key check, no secret-presence check. A truncated/empty `budgets.yaml` makes `load_budgets()["budgets"].get("per_pod_limits", {})` return `{}` and **silently disarms the spend cap** on a live trader. Config load is exactly the "validate at boundaries" line the repo mandates.
- **Recommendation:** Minimal validation layer: assert required top-level keys + types (e.g. `daily_limits.total_spend_limit_usd` is a positive number; agent entries have `default_model_label`/`allowed_task_types`). Fail fast with a clear message.
- **Fix-safety:** 🟢 only changes behavior on already-broken config; test with empty/missing-key YAML.

### C6 — CI runs no tests; nothing gates a prod pull  🟢
- **Location:** `.github/workflows/deploy.yml:38-60`
- **Why:** The only workflow is a manual `workflow_dispatch` on a self-hosted (on-VM) runner that pulls + reinstalls + restarts, then `systemctl is-active`/curl. It **never runs pytest** — the 112-file suite is not a gate. Directly contradicts the "never deploy untested code" rule; nothing stops a broken `master` from landing on the live box. (Secrets correctly never leave the VM.)
- **Recommendation:** Add a `push`/`pull_request` CI job on a GitHub-hosted runner (no secrets) that runs `pip install -r requirements.txt` + `pytest` + the validate/readiness checks; make the deploy job `needs:` the green test job (or run pytest as a fatal pre-step).
- **Fix-safety:** 🟢 additive workflow; doesn't change the deploy path until you gate on it.

### C7 — No Alpaca account-identity guard (CC can silently trade the bot's account)  🔴→🟢 (env-gated)
- **Location:** `runner/ledger/alpaca_paper.py:881-882,900,1749-1750`; `runner/ledger/equity_history.py:69,182,185,228`; `runner/ledger/market_clock.py:79-86`; dead guard `runner/ledger/account_mode.py` (imported by nothing in `runner/`)
- **Why:** Six call sites independently read `ALPACA_API_KEY`/`SECRET` with `paper=True` and verify nothing about *which* account the keys unlock. The repo's hard rule is bot ≠ CC paper account; `account_mode.py` advertises a fail-closed isolation check but is wired into nothing. A `.env` mixup corrupts both books with no error.
- **Recommendation:** Centralize Alpaca cred loading in one helper that calls `get_account()` once and asserts `account_number == TONY_ALPACA_ACCOUNT_ID`. **Env-gated:** unset → warn once, don't halt; set → fail-closed. Wire (or delete) `account_mode.py` so it stops implying a guarantee it doesn't provide.
- **Fix-safety:** 🟢 to land the env-gated mechanism now; 🔴 to make it load-bearing you must supply Tony's real account id (then it can fail-closed).

### C8 — `run_cycle()` god-function + no real worker timeout (ghost-worker double-spend)  🟡
- **Location:** `runner/main.py:1235-1346`, dispatch loop `1297-1318`
- **Why:** `run_cycle()` inlines ~25 concerns in near-identical try/except blocks. Worse, `future.result(timeout)` only stops *waiting* — a Python thread can't be killed, so a worker stuck in a long LLM/tool call keeps running and keeps calling `record_spend` after the cycle already moved its task to `failed/` and released the lock (the precise double-spend the stale-task reaper was bolted on to paper over).
- **Recommendation:** Extract the post-dispatch ledger-maintenance and proactive-push sequences into named helpers; move heavy LLM work to a cancellable process pool, or thread an explicit deadline/cancel-token into `AgentBase.run`'s step loop so a timed-out task stops issuing new calls.
- **Fix-safety:** 🟡 extraction is safe; the execution-model change touches the money path — soak in staging.

### C9 — Checked-in systemd units contradict the prod layout  🔴
- **Location:** `scripts/systemd/execution-loop.service:8-11`, `improvement-loop.service:7-10` (`/home/ubuntu/ai-ops`, `User=ubuntu`, `EnvironmentFile=…/.env`) vs `scripts/deploy/install_cc_dashboard.sh:54` ("No EnvironmentFile on purpose") and CLAUDE.md (`/opt/command-center`, `cc-runner`, `load_dotenv`)
- **Why:** The checked-in units reference a different path, user, and env strategy than the documented production target; deploying from them would fail to start or load the wrong `.env`. Two competing deployment generations coexist in the repo.
- **Recommendation:** Reconcile to one path/user/env strategy or delete the stale units.
- **Fix-safety:** 🔴 confirm the real VM layout (does `update_vm.sh` own the live unit?) before rewriting/deleting.

---

# 2. MEDIUM

### M1 — Shared JSON-I/O helper (kill ~12 copies + fix non-atomic writes)  🟢
- **Location:** fail-soft `_load` clones in `alpaca_paper.py:607`, `tony_realized.py:43`, `tony_scorecard.py:169`, `research_queue.py:51`, `revenue.py:9`, `runway.py:28`, `equity_history.py:27`, `position_meta.py:41`, + inline copies in `tony_verdict/insights/ideas/nudges`, `market_regime.py:124`; atomic-write clones in `budget.py:35`, `runway.py:44`, `position_meta.py:49`, `tony_scorecard.py:93`, `tony_bridge.py:84`; **non-atomic** `revenue.py:24`; tool-side state `email_sender.py:55`, `cold_export.py:51`, `telegram_inbox.py:54`, `notify_policy.py:58`, `telegram_policy.py:67`
- **Why:** 8+ near-identical readers already diverged (some distinguish corrupt vs missing, most don't); `revenue.py` `_save` is a plain `write_text` so a crash corrupts the file the runway/doomsday gate trusts. The tool-side dedup ledgers are the *don't-double-email-a-real-business* safety mechanism and are read-modify-write with no temp+rename.
- **Recommendation:** One `runner/ledger/_jsonio.py` (`load_list`/`load_dict`/`atomic_write_json`); route every module + tool state file through it.
- **Fix-safety:** 🟢 mechanical; keep behavior identical, add empty/corrupt-file tests.

### M2 — Shared markdown-table / CRM parser (kill 6+ copies)  🟢
- **Location:** `dashboard/server.py:308-328,367-387,556-573`; `runner/tools/opportunity.py:63-77,194-205,229-246`; `outreach_crm.py:42-61`; `crm_dedup.py:6-35`; `social_dm.py:111`; `scripts/{opportunity_synthesis,outreach_synthesis,merge_crm,merge_dm_queue,backfill_outreach,design_synthesis}.py`
- **Why:** The pipe-delimited parse + name-normalize + cell-clean is re-implemented with subtly different column counts; column-index drift between copies is latent data corruption (server already carries scar-tissue comments about bad rows).
- **Recommendation:** One `parse_md_table`/CRM row-loader in a shared module; server + scripts + tools import it.
- **Fix-safety:** 🟢 pure refactor with CRM tests.

### M3 — Move API tokens out of URL query params into headers  🟢
- **Location:** `runner/tools/social.py:75-84,92-96,150-158`; `social_dm.py:79-83,92-100`; `cold_export.py:142,161`
- **Why:** `access_token`/`api_key` in `params=` lands in access/proxy logs and is echoed back to the LLM on error (`r.text[:200]`, `str(result)[:200]`). `email_sender.py:124` shows the correct Bearer-header pattern.
- **Recommendation:** Use `Authorization: Bearer` for Meta Graph calls; for Smartlead's mandated key-in-query, scrub `api_key=…` from any returned error string.
- **Fix-safety:** 🟢 Meta accepts header auth; behavior-preserving.

### M4 — Single `_fail_task()` for timeout/paused cleanup  🟢
- **Location:** `runner/main.py:1304-1318` and `689-698`
- **Why:** Cycle-level timeout and `PROSPECTOR_PAUSED` early-out skip `update_agent_state`, so the dashboard shows an agent permanently `working` on an abandoned task and no failure memory is written. State drift accumulates in a 24/7 system.
- **Recommendation:** Route all failure/pause paths through one `_fail_task(task_id, role_id, reason)` (move + unlock + `update_agent_state`).
- **Fix-safety:** 🟢 additive bookkeeping.

### M5 — Task dedup via parsed frontmatter, not substring grep  🟢
- **Location:** `runner/tools/task_creator.py:49-64`; `runner/main.py:356-370,470-483`
- **Why:** Duplicate-spawn prevention hinges on `f"assigned_agent: {agent}" in content` as a plain substring — the Atlas spawn template (`main.py:289-344`) literally contains those strings in a fenced block, so a legit spawn can be suppressed (or a dead loop masked). It's parsing YAML with `in`.
- **Recommendation:** Use `tasks/reader.py:parse_task_file` and compare parsed frontmatter fields; add a test with a body that quotes the markers.
- **Fix-safety:** 🟢 swaps fragile match for the existing parser.

### M6 — Thread-safety lock around the Vertex token refresh  🟢
- **Location:** `runner/agents/base.py:19-30,120-121` (with the 4-thread pool in `main.py:1297`)
- **Why:** `_vertex_token()` mutates module-global creds/Request with no lock while up to 4 worker threads call it; two threads refreshing the same `Request` can race (`google.auth` isn't documented thread-safe) → intermittent auth errors under exactly the load the retry logic targets.
- **Recommendation:** Guard lazy-init + refresh with a `threading.Lock`.
- **Fix-safety:** 🟢 additive lock.

### M7 — Move outreach post-run validation out of `AgentBase`  🟢
- **Location:** `runner/agents/base.py:258-285` + duplicated contract in `runner/agents/prompts.py:68-85`
- **Why:** The generic agent loop hard-codes outreach-specific logic and detects intent by substring-matching serialized JSON args (`'"write"' in arguments`); the same rule is also in the prompt, so two enforcement points can drift.
- **Recommendation:** Pluggable `post_run_check(role_id, messages)` hook; parse recorded `tool_calls` args as JSON.
- **Fix-safety:** 🟢 behavior-preserving with existing tests.

### M8 — Market-clock holiday table expires 2027 + is sole authority on API failure  🟢
- **Location:** `runner/ledger/market_clock.py:39-60`, consumed at `:72,124`, fallback wired `:103-106`; gate at `alpaca_paper.py:1439`
- **Why:** `_alpaca_clock_open()` returns `None` on any exception → falls back to the pure-ET check, making the hard-coded holiday set the only authority. It stops at 2027-12-24, so from 2028 every holiday reads as a trading day; half-days return full-session open. Entry gate could fire on a closed holiday during any API blip.
- **Recommendation:** Use `exchange_calendars`/`pandas-market-calendars`, or fail-closed (return "closed") + log when `now.year` exceeds the table's max year.
- **Fix-safety:** 🟢 additive/conservative.

### M9 — `date.today()` → `trading_day()` in Tony research writers  🟢
- **Location:** `runner/tools/tony_insights.py:33`, `runner/tools/tony_ideas.py:34` (dedup per `(date,symbol)` at `tony_ideas.py:47`)
- **Why:** `tony_verdict.py:21-30` documents the ET bug and uses `trading_day()`; these siblings still use `date.today()`, so post-8 PM ET ideas/insights are stamped *tomorrow*, corrupting same-day dedup.
- **Recommendation:** Swap both to `market_clock.trading_day()`.
- **Fix-safety:** 🟢 one-line each.

### M10 — Single verdict vocabulary (3 `_OPEN` sets must stay lockstep)  🟢
- **Location:** `alpaca_paper.py:91`, `runner/tools/tony_book.py:166`, `runner/ledger/tony_scorecard.py:412`; authoritative `runner/tools/tony_verdict.py:43`
- **Why:** `{"reaffirm","adjust","override"}` is redeclared 3× across the modules that *execute*, *grade*, and *display* verdicts; adding/reclassifying one silently desyncs them (executed-but-never-graded).
- **Recommendation:** Define `VERDICTS`/`OPENING_VERDICTS`/`BULLISH_VERDICTS` once in `tony_verdict.py`; import everywhere; add `OPENING_VERDICTS ⊆ VERDICTS` test.
- **Fix-safety:** 🟢

### M11 — Equity feed-outage handling (don't feed stale/zero to the breaker)  🟢
- **Location:** `runner/ledger/equity_history.py:75-77,94-95,106,119-130,196-198`; consumed by `drawdown_breaker.max_drawdown_pct`
- **Why:** Price/equity readers swallow every exception → empty; `mark_live` then falls back to Alpaca's stale `current_price` (docstring: lags several %), and missing price marks at `$0`. A transient outage produces a multi-percent-wrong drawdown feeding the circuit breaker as if real.
- **Recommendation:** Distinguish "feed down" from "no positions"; mark snapshot degraded so stale/zero doesn't reach the breaker; guard `current_price <= 0`.
- **Fix-safety:** 🟢

### M12 — `bot_equity()` unguarded JSON parse  🟢
- **Location:** `runner/ledger/equity_history.py:136-174,215-216`; `snapshot()` calls it outside try at `:143-151`
- **Why:** Per-row `o["symbol"]`/`float(entry)` outside try; one malformed row aborts the whole equity snapshot for the cycle.
- **Recommendation:** Per-row try/except skip (as `tony_realized.reconcile_from_fills` already does).
- **Fix-safety:** 🟢

### M13 — One env-var name for `equity-history.json`  🟢
- **Location:** writer `equity_history.py:18-20` (`TONY_EQUITY_HISTORY`) vs reader `drawdown_breaker.py:194-197` (`TONY_EQUITY_HISTORY_FILE`)
- **Why:** Both default the same so it works by accident; relocating the file (e.g. the mandated staging soak) splits writer/reader → breaker silently reads empty and never halts. A footgun in the required staging workflow.
- **Recommendation:** Standardize on one name (via the shared `workspace_path` helper).
- **Fix-safety:** 🟢

### M14 — IMAP: cap fetch size/count + sanitize bodies  🟢
- **Location:** `runner/tools/inbox_reader.py:261-340`, `_body_text:94-109`, fetch `:291`; interest classifier `_has_strong_interest`
- **Why:** Fetches full RFC822 for caller-supplied `max_messages` (no ceiling) and decodes every part before truncation → memory spike/stall; untrusted body flows to the LLM unsanitized; negation windows are brittle.
- **Recommendation:** Clamp `max_messages`, fetch headers + bounded body slice, sanitize body/subject via the guard; treat interest detection as advisory.
- **Fix-safety:** 🟢 (outreach paused).

### M15 — `send_email` input hardening + real unsubscribe check  🟢
- **Location:** `runner/tools/email_sender.py:88-119`, `_EMAIL_RE:15`, `_stage_for_review:78-81`
- **Why:** `to_name`/`subject` are LLM-supplied and written verbatim into the SendGrid payload and the review-queue markdown — a newline corrupts the queue / rendered email. The unsubscribe check is "substring anywhere," so CAN-SPAM compliance is nominal.
- **Recommendation:** Strip CRLF + clamp length on `to_name`/`subject`; require a real opt-out directive near the footer.
- **Fix-safety:** 🟢 (outreach paused).

### M16 — Consistent tool registration (one source of truth)  🟢
- **Location:** registry `runner/agents/tool_runner.py:59-101`; mismatch `enrich_contacts` (registry) vs `enrich_site_contacts` (`apify.py:43`); `crm_dedup`/`landing`/`opportunity.read_ledger` never registered; per-tool `TOOL_SPEC` dicts unused
- **Why:** Specs declared but registry registers bare callables → non-obvious which schemas reach the model; name divergence + unregistered tools make the dispatch surface easy to get subtly wrong.
- **Recommendation:** Register by `TOOL_SPEC["name"]`; assert name==spec at import; remove/justify unexposed specs.
- **Fix-safety:** 🟢 mechanical + import-time assert.

### M17 — `dispatch_tool` shouldn't flatten every error identically  🟢
- **Location:** `runner/agents/tool_runner.py:13-16`
- **Why:** Every tool exception (network blip, real bug, missing key, budget-exceeded) becomes the same `{"error": str(exc)}` fed back to the model, which "self-corrects" by retrying and burning money against an unfixable error; no logging at dispatch.
- **Recommendation:** Log with `exc_info`; distinguish retryable vs terminal so the loop stops hammering unrecoverable tools.
- **Fix-safety:** 🟢 additive.

### M18 — Reconcile the inverted config/example split  🟢
- **Location:** `config/` vs `runner/config.py`
- **Why:** 7 `*.example.yaml` (`revenue-pods`, `guardrails`, `tools`, `dashboard`, `agent-models`, `schedules`, `star-office-ui`) have no real counterpart and are read by no code; the 3 configs actually loaded (`automation-level`, `spawn-schedules`) + `brand.yaml` ship no template; `brand.yaml` points to a non-existent `revenue-pods.yaml`.
- **Recommendation:** Either load the missing real configs or delete the dead examples; add templates for the loaded ones; fix the brand→revenue-pods pointer.
- **Fix-safety:** 🟢 confirm no setup script copies the examples first.

### M19 — `budgets.yaml` ⇄ example ⇄ validator drift  🟢
- **Location:** `config/budgets.yaml` vs `config/budgets.example.yaml:34` and `scripts/validate-budgets.ps1:51`
- **Why:** Real config omits `escalate_at_percent_of_daily_budget` (the validator marks it REQUIRED → validator fails or is never run) and adds `per_pod_limits` (absent from example). The escalate field is referenced by no Python.
- **Recommendation:** Drop the vestigial field from validator+example, or restore it; add `per_pod_limits` to the example.
- **Fix-safety:** 🟢

### M20 — Strip scrapped-Etsy content from `brand.yaml`  🟢
- **Location:** `config/brand.yaml`
- **Why:** Bottom half is leftover ThePromptVaultUS config ($6–$14 prompt packs, Etsy tags) for a pod scrapped 2026-05-23; an agent could act on stale guidance. No `load_brand` in `config.py`.
- **Recommendation:** Strip the Etsy block, or delete the file if revenue-pods owns brand data (grep first).
- **Fix-safety:** 🟢

### M21 — Consolidate the three eval locations  🟢
- **Location:** `runner/eval/` (LIVE — imported), `evals/tony/` (not imported), `evaluations/` (17 README/template files, unread)
- **Why:** Three names for "evaluation" guarantees confusion about where eval logic lives.
- **Recommendation:** Keep `runner/eval/`; move `evaluations/` rubrics into `docs/` and drop empty README dirs; document or delete `evals/tony/` (check no cron/CI calls it).
- **Fix-safety:** 🟢 for the docs scaffolding.

### M22 — Delete the duplicate `dashboard-state.json` orphan  🟢
- **Location:** live `workspace/dashboard-state.json` (writer `runner/state/writer.py:6`, reader `dashboard/server.py:36`) vs orphan `workspace/dashboard/dashboard-state.json` (written only by `scripts/dashboard-export-state.ps1:209`)
- **Why:** The two differ (615 B vs ~14 KB); anyone opening the nested one sees stale state. Committing runtime state dirties the tree every run.
- **Recommendation:** Delete the orphan; gitignore both runtime-state paths; retire the PS export flow if dead.
- **Fix-safety:** 🟢 orphan unread by the Python dashboard.

### M23 — Pin dependencies (lockfile)  🟢
- **Location:** `requirements.txt` (all `>=`, no upper bound, no lock; `update_vm.sh` installs fresh on the VM)
- **Why:** A breaking minor of FastAPI/uvicorn/alpaca-py/openai/anthropic can silently land on prod at deploy time — the "tested ≠ deployed" gap the rules try to prevent. (Three LLM SDKs is intentional: Anthropic + OpenAI/OpenRouter + Vertex are all wired in `base.py`.)
- **Recommendation:** Add `requirements.lock` via `pip-compile`/`uv`; install from the lock in `update_vm.sh`.
- **Fix-safety:** 🟢 capture current resolved versions first.

### M24 — Fix `improvement_loop.py` docstring + token param  🟢
- **Location:** `scripts/improvement_loop.py:4` ("calls Claude API"), `:20` (`from openai import OpenAI`), `:196-208` (Gemini via OpenAI-compat shim, `max_tokens=8192`)
- **Why:** This nightly loop **auto-commits rewritten agent prompts**; a reader trusting the docstring misjudges the model/guardrails. `max_tokens` may be the wrong param name for the compat endpoint (silently ignored).
- **Recommendation:** Correct the docstring to Gemini; verify the token-cap param for the OpenAI-compat endpoint. (Centralize the client construction — see M1/theme.)
- **Fix-safety:** 🟢 docstring/param; model/endpoint switch would be 🟡.

### M25 — Delete dead `_runner_loop.py`  🟢
- **Location:** `scripts/_runner_loop.py:1-2` (BOM + `sys.path.insert(0, r'C:\Users\alexa\Downloads\…')`)
- **Why:** Hard-coded Windows path can't run on the Linux VM; duplicates `launch.py`/`run_cycle.py`; swallows every cycle exception to stdout. Pure confusion in an ops-sensitive dir.
- **Recommendation:** Delete (verify nothing references it).
- **Fix-safety:** 🟢

### M26 — Tame the PowerShell script sprawl  🟢
- **Location:** `scripts/*.ps1` (22 files) vs the `.sh`/`.py` that actually deploy
- **Why:** None run on the Linux prod box; several duplicate bash/Python concepts; the `validate-*.ps1` family has no Linux equivalent so those checks never run in CI/VM. Dormant cruft inviting three-way drift.
- **Recommendation:** Move dev-only PS to `scripts/win/` (clearly labeled) or port the validators to one Python checker the VM + CI can run.
- **Fix-safety:** 🟢 confirm no Windows-dev dependency.

### M27 — Make the no-assert tests actually assert  🟢
- **Location:** `tests/runner/test_cron_runner.py:28`, `test_improvement_loop.py:5,28`, `test_locker.py:26`, `test_decision_audit.py:82` (9 total); thin locker coverage (concurrency only in `test_stress_round2.py`)
- **Why:** 9 tests call code with zero assertions ("didn't throw") → false coverage on the self-improvement loop and lock-release. Stale-lock expiry/reaper is only in the 531-line stress file.
- **Recommendation:** Add return-value assertions; add a stale-lock-expiry + TTL-boundary case directly to `test_locker.py`.
- **Fix-safety:** 🟢

### M28 — Long-only assumption in realized P&L feeds the breaker  🟢
- **Location:** `runner/ledger/tony_realized.py:24-40,59-60`; consumed by `drawdown_breaker.py:43-47`; stale docstring `tony_realized.py:8`
- **Why:** P&L and exit-reason assume a long; a profitable short would log as a loss → could mis-trip the breaker. Tony is long-only today (hence Medium) but the invariant is undefended; `record_realized` may now be dead (live path is `reconcile_from_fills`).
- **Recommendation:** Assert long-only at the boundary (or carry side + direction-aware P&L); fix the stale docstring; confirm/remove dead `record_realized`.
- **Fix-safety:** 🟢

### M29 — `runner/paths.py` for cross-repo path resolution  🟢
- **Location:** `alpaca_paper.py:28-29`, `tony_bridge.py:24-28`, `tony_scorecard.py:20-21`, `research_queue.py:27` (+ ~12 `…/workspace/x.json` reconstructions)
- **Why:** Modules reach the sibling `TradingBotAgentProject` checkout by counting `.parent` hops — positional (moving a file repoints prod data) with no existence check (missing checkout → silent empty reads).
- **Recommendation:** One `runner/paths.py` exposing `WORKSPACE`/`REPORTS_DIR`/`VAULT` resolved from explicit env config, failing loudly when missing.
- **Fix-safety:** 🟢

### M30 — Remove dead-but-registered `etsy.py`  🟡
- **Location:** `runner/tools/etsy.py`; registered `runner/agents/tool_runner.py:28,69`; skill ref `config/agents.yaml:206`; pod scrapped per `config/brand.yaml`
- **Why:** A dispatchable tool that hits the live Etsy API for a dead brand — a stray/hallucinated task could make real API writes.
- **Recommendation:** Unregister + delete; prune the `etsy_listing_strategy` skill refs.
- **Fix-safety:** 🟡 touches the live tool registry on a 24/7 system; confirm no active task references it, then remove on dev.

### M31 — HTTP provider skeleton + ambiguous-timeout idempotency util  🟢
- **Location:** six near-identical providers `runner/tools/web.py:264-498`; "accepted-then-timeout → record as sent" re-implemented in `email_sender.py:135-140`, `social_dm.py:59-65`, `cold_export.py:162-210`
- **Why:** Cross-cutting changes (connect timeout, retry, shared client) mean editing 6 blocks; the "record on ambiguous timeout to avoid double-send" rule — the highest-consequence behavior — is hand-rolled 3× with different trigger strings.
- **Recommendation:** Factor the provider skeleton (key, request-builder, parser) and one shared idempotency util used by all send tools.
- **Fix-safety:** 🟢 keep behavior identical; add a timeout-branch test.

### M32 — Harden the server-side note filter (pairs with C4)  🟢
- **Location:** `dashboard/server.py:360-363`
- **Why:** Blocks `|`/newlines (table structure) but not `< > "` (the XSS sink the notes feed).
- **Recommendation:** Reject/encode HTML-significant chars, or store encoded + escape on render.
- **Fix-safety:** 🟢

### M33 — Pause flags / routing / spawn-gate → single config source  🟡
- **Location:** `runner/main.py:120-132`; `runner/tasks/router.py:18-31`; `runner/tools/task_creator.py:84-91`
- **Why:** `OUTREACH_PAUSED`/`PROSPECTOR_PAUSED`/`MAX_CONCURRENT` are module constants needing a code-change+deploy to toggle a pod; `agents.yaml`'s `enabled` is ignored by routing; the pipeline's direct `create_task` calls can be silently throttled. Three overlapping gates to answer "why didn't this pod run."
- **Recommendation:** Move switches into config read per-cycle; make routing honor one `enabled` source; have the pipeline check `spawn_allowed` explicitly.
- **Fix-safety:** 🟡 changes live pod gating — stage.

### M34 — `move_task` atomic rename via tracked path  🟡
- **Location:** `runner/tasks/transitions.py:10-28,31-38`
- **Why:** `move_task` does `glob(f"*{task_id}*.md")` and takes `matches[0]` — a substring/prefix id moves the wrong file; the read→write-dst→unlink-src is non-atomic (crash leaves the task in two dirs → re-run); `write_task_output` appends a fresh section every call (no idempotency).
- **Recommendation:** Move the exact `file_path` from `parse_task_file` with `os.replace`; guard `write_task_output` against re-append.
- **Fix-safety:** 🟡 core task lifecycle — stage.

### M35 — Split the `alpaca_paper.py` god-file (1873 lines)  🟡
- **Location:** `runner/ledger/alpaca_paper.py` (planning `95-818`, `_Broker` adapter `879-1159`, reconcile `1162-1179`, notify `1182-1335`, sync `1338-1740`, dashboard data proxy `1742-1873`)
- **Why:** Five responsibilities in one module force whole-file reads for any change and drove much of the duplication. (Its pure planning layer is genuinely good — preserve it.)
- **Recommendation:** Split along existing seams: `tony_planning.py`, `tony_broker.py`, `tony_sync.py`, `tony_notify_book.py`, and move the SPY/Stooq dashboard proxy out of the trading module.
- **Fix-safety:** 🟡 pure code-move but huge import surface — stage + full suite.

### M36 — Stop string-patching minified JS in `build_tony_dashboard.py`  🟡
- **Location:** `scripts/build_tony_dashboard.py:19,92-339` (15 literal `.replace()` anchors against a minified bundle; `/tmp/tony_design_unzip/...` fallback)
- **Why:** Regenerates the 275 KB `tony.html` by matching exact minified snippets; any re-export breaks an anchor and aborts the build; the inlined live-wiring JS is unmaintainable/untestable.
- **Recommendation:** Treat the live wiring as real source (a small JS module the page loads); drop the `/tmp` fallback; snapshot-test the anchors.
- **Fix-safety:** 🟡 production page generator — stage.

### M37 — Make `backfill_outreach.py` idempotent  🟡
- **Location:** `scripts/backfill_outreach.py:141,190-270`
- **Why:** Re-running re-sends to every `call_queued` prospect (no sent guard); CRM is rewritten in one `write_text` AFTER sends — a failed write leaves sends untracked → re-sent next run. Duplicate cold outreach = deliverability + reputational risk.
- **Recommendation:** Per-row sent marker; write CRM before/transactionally with sends; snapshot before overwrite; archive if backfill is complete.
- **Fix-safety:** 🟡 live outreach — only with explicit operator intent.

---

# 3. NICE-TO-HAVE

### N1 — Separate the Obsidian vault from the code repo  🟢 (needs sign-off)
- **Location:** `.obsidian/`, `Untitled{,' 1',' 2'}.canvas`, `notes/`, `training/` (17 files, dormant-pod playbooks), `tools_mastery/`, `prompts/`, `shortcuts/`, `.superpowers/`, top-level `2026-05-22.md`, `CRM.md`, `Enterprise SaaS.md`
- **Why:** None referenced by code (grep-verified); bloats the repo to ~1009 tracked files and makes `git status`/search noisy.
- **Recommendation:** Move the genuine KB to a separate vault repo or `docs/kb/`; delete editor state + empty `Untitled*.canvas`; at minimum gitignore.
- **Fix-safety:** 🟢 no code refs — but a large removal; get explicit sign-off on the exact set.

### N2 — Purge scrapped-pod artifacts under `workspace/`  🟢
- **Location:** `workspace/social/ready-to-post/*` (24), `workspace/products/POD-ETSY-*`, top-level `workspace/POD-DIG-001-*`/`POD-LEAD-001-*`/`POD-AFF-001-*`, `workspace/outputs/*thepromptvalutus*`
- **Why:** ThePromptVaultUS output (pod scrapped 2026-05-23). `workspace/social/` is live (written by `social.py`) but the *contents* are dead and versioned as source.
- **Recommendation:** Delete the POD-* artifacts; gitignore `workspace/social/ready-to-post/` + `workspace/products/`.
- **Fix-safety:** 🟢 verify no test fixture reads a specific POD- file.

### N3 — Delete the em-dash filename + harden the slugifier  🟢
- **Location:** `workspace/social/ready-to-post/20260522-180846-…—-yo.{json,script.md}` (em-dash U+2014 + apostrophe); slug fn in `runner/tools/social.py`
- **Why:** Non-ASCII em-dash + apostrophe can break `git checkout`/extraction on Windows (the dev platform) and confuse globs; the slugifier will recur it.
- **Recommendation:** Delete the two files (dead anyway); restrict the slug to `[a-z0-9-]`.
- **Fix-safety:** 🟢

### N4 — Clean `.gitignore` slop  🟢
- **Location:** `.gitignore:54` (`=*` stray pip-redirect artifact), `:60-61` (near-duplicate archive rules)
- **Why:** `=*` ignores any path starting with `=` — harmless but baffling; the rot makes the ignore file untrustworthy.
- **Recommendation:** Delete line 54; collapse to a single `workspace/tony-verdicts-archive.json*`.
- **Fix-safety:** 🟢

### N5 — Retire `setup_windows.py` + prune stale model lists  🟢
- **Location:** `runner/scheduler/setup_windows.py` (whole file); `MODELS`/`MODEL_PRICING`
- **Why:** Shells out to `schtasks` and references a cadence the inline `run_cycle` no longer implements — dead on the Linux VM but reads as live wiring; the model tables still list dormant-pod roles + unrouted models.
- **Recommendation:** Move under `dev/`/`windows/` (or delete) with a pointer to the real systemd unit; prune/justify unused model entries.
- **Fix-safety:** 🟢 non-executing; confirm no dev import.

### N6 — `launch.py`: real readiness check + single port constant  🟢
- **Location:** `scripts/launch.py:30,62-72`
- **Why:** Reports "Dashboard running" after a fixed `sleep(2)` with `stdout/stderr=DEVNULL` and no returncode check — a crashed uvicorn looks healthy; the port is duplicated (drift vs deploy scripts).
- **Recommendation:** Poll the socket/`/state` before declaring success; surface uvicorn stderr on failure; define the port once.
- **Fix-safety:** 🟢

### N7 — Separate meter for the off-hours research lane  🟡
- **Location:** `runner/main.py:1242-1248` + `runner/ledger/budget.py:100-118`
- **Why:** `is_budget_exceeded(off_hours=True)` checks a separate cap but `get_daily_spend()` is the *same* `total_usd` the daytime lane uses, so overnight research can consume the next day's budget before open — hard to reason about, entangled with C1's reset.
- **Recommendation:** Track off-hours spend in its own `by_lane` bucket.
- **Fix-safety:** 🟡 changes spend accounting — bundle with C1, stage.

---

## Status table

| ID | Title | Tier | Fix | Status |
|----|-------|------|-----|--------|
| C1 | UTC budget rollover resets spend caps | Critical | 🟢 | ✅ |
| C2 | web_fetch SSRF | Critical | 🟢 | ✅ |
| C3 | web_research bypasses injection guard | Critical | 🟢 | ✅ |
| C4 | Dashboard stored XSS | Critical | 🟢 | ✅ |
| C5 | config.py no validation | Critical | 🟢 | ✅ |
| C6 | CI runs no tests | Critical | 🟢 | ✅ |
| C7 | No Alpaca account-identity guard | Critical | 🟢/🔴 | ✅ (env-gated; pin `TONY_ALPACA_ACCOUNT_ID` to arm) |
| C8 | run_cycle god-fn + no real timeout | Critical | 🟡 | ☐ |
| C9 | systemd units wrong layout | Critical | 🔴 | ☐ (needs VM-layout confirm) |
| M1 | Shared JSON-I/O helper | Medium | 🟢 | ☐ |
| M2 | Shared markdown-table parser | Medium | 🟢 | ☐ |
| M3 | Tokens → headers | Medium | 🟢 | ☐ |
| M4 | Single _fail_task() | Medium | 🟢 | ☐ |
| M5 | Task dedup via frontmatter | Medium | 🟢 | ☐ |
| M6 | Vertex token lock | Medium | 🟢 | ☐ |
| M7 | Outreach post-run hook | Medium | 🟢 | ☐ |
| M8 | Market-clock holiday/fallback | Medium | 🟢 | ☐ |
| M9 | date.today()→trading_day() | Medium | 🟢 | ✅ |
| M10 | Single verdict vocabulary | Medium | 🟢 | ☐ |
| M11 | Equity feed-outage handling | Medium | 🟢 | ☐ |
| M12 | bot_equity() parse guards | Medium | 🟢 | ☐ |
| M13 | One equity-history env var | Medium | 🟢 | ✅ |
| M14 | IMAP caps + sanitize | Medium | 🟢 | ☐ |
| M15 | send_email hardening | Medium | 🟢 | ☐ |
| M16 | Tool registration consistency | Medium | 🟢 | ☐ |
| M17 | dispatch_tool error classify | Medium | 🟢 | ☐ |
| M18 | Config/example reconcile | Medium | 🟢 | ☐ |
| M19 | budgets.yaml drift | Medium | 🟢 | ☐ |
| M20 | brand.yaml strip Etsy | Medium | 🟢 | ✅ |
| M21 | Consolidate eval dirs | Medium | 🟢 | ☐ |
| M22 | Delete dashboard-state orphan | Medium | 🟢 | ✅ |
| M23 | Pin requirements | Medium | 🟢 | ☐ |
| M24 | improvement_loop docstring/param | Medium | 🟢 | ☐ |
| M25 | Delete dead _runner_loop.py | Medium | 🟢 | ✅ |
| M26 | PowerShell sprawl | Medium | 🟢 | ☐ |
| M27 | No-assert tests + locker | Medium | 🟢 | ☐ |
| M28 | Long-only P&L guard | Medium | 🟢 | ☐ |
| M29 | runner/paths.py | Medium | 🟢 | ☐ |
| M30 | Remove etsy.py | Medium | 🟡 | ☐ |
| M31 | HTTP skeleton + idempotency util | Medium | 🟢 | ☐ |
| M32 | Harden server note filter | Medium | 🟢 | ✅ |
| M33 | Pause flags → config | Medium | 🟡 | ☐ |
| M34 | move_task atomic rename | Medium | 🟡 | ☐ |
| M35 | Split alpaca_paper.py | Medium | 🟡 | ☐ |
| M36 | build_tony_dashboard JS source | Medium | 🟡 | ☐ |
| M37 | backfill_outreach idempotency | Medium | 🟡 | ☐ |
| M38 | Untrack committed .pyc | Medium | 🟢 | ✅ |
| N1 | Separate Obsidian vault | Nice | 🟢 | ☐ |
| N2 | Purge scrapped-pod artifacts | Nice | 🟢 | ☐ |
| N3 | em-dash filename + slug | Nice | 🟢 | ☐ |
| N4 | .gitignore cleanup | Nice | 🟢 | ✅ |
| N5 | Retire setup_windows.py | Nice | 🟢 | ✅ |
| N6 | launch.py readiness | Nice | 🟢 | ☐ |
| N7 | Off-hours lane meter | Nice | 🟡 | ☐ |
