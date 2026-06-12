# Handoff — Build the scanner-bot staging twin (dual-repo session)

**Paste this whole file as the opening prompt of a new Claude Code session that has BOTH
repos attached**, or just point that session at `docs/SCANNER_STAGING_HANDOFF.md` in the
command-center checkout. It assumes the session can see both working trees side by side.

---

## 0. Repos this session needs

| Role | Repo | VM path |
|---|---|---|
| Command Center (CC) — Tony, runner, dashboard | `steveguhlore/ai-operations-command-center` | `/opt/command-center` |
| Scanner bot (the "trading bot") | `steveguhlore/TradingBotAgentProject` *(repo NAME; confirm exact owner/slug)* | **`/opt/trading-bot`** |

**Confirmed VM layout (verified 2026-06-12):**
- The scanner's checkout is **`/opt/trading-bot`**. `/opt/TradingBotAgentProject` exists as a
  **symlink → `/opt/trading-bot`** (so old docs referencing `TradingBotAgentProject` paths still
  resolve). Use `/opt/trading-bot` as the canonical path.
- Scanner services: **`tradingbot-api`** + **`tradingbot-web`** (plus a `dashboard-web` npm
  frontend). CC service: `cc-runner`. All `active`.
- **Shared reports dir = `/opt/trading-bot/reports`** (dated subdirs). Prod CC's `.env` overrides
  `TONY_OUTCOMES_FILE` / `TONY_VERDICTS_FILE` / `TONY_RECORD_FILE` to point there explicitly; the
  other three (`TONY_REPORTS_DIR`, `TONY_INSIGHTS_FILE`, `TONY_IDEAS_FILE`) ride the code default
  `/opt/TradingBotAgentProject/reports`, which resolves to the same dir via the symlink.
- Bot→CC pointer: `/opt/trading-bot/config/default_config.yaml` → `command_center_dir: /opt/command-center`.

If the scanner repo isn't attached, attach it before starting (claude.ai/code repo picker, or
ask this session to add the scanner repo). If the picker doesn't list it, install the
Claude GitHub App on that repo first.

**Dev branch discipline (ENFORCED — production runs 24/7):** all work on a dev branch, never
straight to the scanner's deploy branch. CC's current dev branch is `claude/gracious-euler-dAdgn`.
Pick an equivalent dev branch on the scanner repo. Soak before promoting. Do NOT restart or touch
either production service.

---

## 1. The goal in one sentence

The CC staging twin is **already built and shipping** (`/opt/command-center-staging`, port 8766).
Build the **matching staging twin for the scanner bot** so that scanner-code changes can be soaked
overnight against staging-CC — with the whole tandem loop closed inside the staging sandbox and
**zero contact with either production service or the live $1M paper account.**

When done, the workflow for *any* scanner change becomes:
`dev branch → push to scanner staging → soak overnight → promote gate → fast-forward prod`,
exactly mirroring what CC already has.

---

## 2. How the tandem couples (read this before writing anything)

Two repos, coupled only through **files in two directions**:

**Scanner → CC (inbound to Tony):**
- Scanner writes scan/tier reports into the **bridge** dir: `/opt/command-center/bridge/tony-stocks`
- Scanner also writes into the **shared bot reports dir**: `/opt/trading-bot/reports`
- Tony reads both.

**CC → Scanner (outbound from Tony):** production-Tony writes these into the **same bot reports dir**,
and the scanner reads them for grading/feedback:
`tony_stocks_verdicts.json`, `tony_stocks_outcomes.json`, `tony_stocks_record.json`,
`agent_insights.json`, `tony_stocks_ideas.json`.

So the **bot reports dir is the shared exchange** in both directions. That is the surface that must
be isolated, or staging corrupts production grading.

---

## 3. What CC staging already does (your template — mirror it)

Built on the CC side, on the dev branch, already on the VM-deployable kit:

- **`scripts/setup_staging.sh`** — creates `/opt/command-center-staging` as a **git worktree**
  (shares the object store — no duplicate history, ~1 GB total = one extra venv), own `.venv`,
  isolated `.env`, writes a `cc-runner-staging.service` unit to `/tmp` for hand-install. Never
  writes into `/opt/command-center`, never touches the prod `.env`, never restarts `cc-runner`.
  - Dashboard on **127.0.0.1:8766** (prod 8765).
  - **Six shared vars force-overridden** so staging-CC writes its verdicts into
    `/opt/command-center-staging/workspace/trading-reports`, NOT the bot's live reports dir:
    `TONY_REPORTS_DIR`, `TONY_VERDICTS_FILE`, `TONY_OUTCOMES_FILE`, `TONY_RECORD_FILE`,
    `TONY_INSIGHTS_FILE`, `TONY_IDEAS_FILE`. Plus `TONY_BRIDGE_DIR` → staging's own bridge.
  - **Sends hard-off**: Telegram / SendGrid / Instagram disabled, live-trading vars blanked.
  - `--mirror-bridge` installs a 1-min cron copying **new** files from the prod bridge + bot
    reports into staging (read-only against prod; never deletes/overwrites/writes back).
  - **⚠️ One footgun:** by default staging inherits the **production Alpaca paper keys** → it
    would trade the same $1M paper account. For a real soak you MUST drop in a **second free
    Alpaca paper account** (placeholders at the bottom of the staging `.env`).
- **`scripts/promote_staging.sh`** — the gate: full pytest + readiness sweep + `:8766` liveness;
  on all-green prints the exact ff-merge/restart commands. Never pushes/merges/restarts itself.
- **`docs/DEVELOPMENT.md`** — the workflow writeup.

Read all three in the CC checkout before writing the scanner version. Match their structure,
isolation comments, and idempotency.

---

## 4. Your task: `setup_staging.sh` for the scanner repo

Build the scanner equivalent (same recipe), producing `/opt/trading-bot-staging`:

1. **Worktree** of the scanner repo on the dev branch (fall back to clone if worktree fails),
   own `.venv` from the scanner's requirements, isolated `.env`/config.
2. **Close the loop into staging-CC, not prod.** Point the scanner-staging output at
   **staging-CC's** dirs:
   - scan/tier reports → `/opt/command-center-staging/bridge/tony-stocks`
   - shared reports exchange → `/opt/command-center-staging/workspace/trading-reports`
   - whatever env vars / config the scanner uses for its output dir and for reading Tony's
     verdicts back — repoint ALL of them at the staging-CC paths. **Enumerate them by reading
     the scanner code** (look for its reports-dir / output-dir / verdicts-path config), the same
     way CC's script enumerates and overrides its six shared vars. List each one in a comment with
     why, exactly like `setup_staging.sh` does.
3. **Second paper account:** if the scanner places or simulates Alpaca orders, give it the same
   second-paper-account treatment (placeholders + loud warning). If it's read-only market data,
   note that explicitly instead.
4. **Outbound off:** disable any scanner alerts/notifications/posting in staging.
5. **Own service units** — the prod scanner runs `tradingbot-api` + `tradingbot-web` (and a
   `dashboard-web` frontend). Mint `tradingbot-api-staging` / `tradingbot-web-staging` units
   written to `/tmp` for hand-install, on their own ports (prod API is on :8001 per the handoffs —
   pick free ports for staging), logs to a staging logs dir. Never restart or touch the production
   scanner services.
6. **Idempotent** re-runs (don't clobber a filled-in staging `.env`).
7. Tests + a short `docs/DEVELOPMENT.md` (or update the existing one) on the scanner side.

**Important interaction with `--mirror-bridge`:** when you're testing *scanner* changes, you want
the **staging scanner** generating the bridge files, NOT the prod-mirror cron. So: run CC staging
**without** `--mirror-bridge` (or stop that cron) while a scanner twin is live, otherwise prod scan
output and staging scan output both land in staging-CC's bridge. Document this either/or clearly.

---

## 5. The blind spot this whole exercise exists to cover

Because staging-CC's verdict write-back is severed from the bot's live reports dir, a CC change that
alters the **format** of the files Tony writes (the five `tony_stocks_*` / `agent_insights` files)
won't be caught by CC staging alone — only a scanner twin reading staging-CC's output catches a
parser break. **Any change to the verdict/outcome/record schema, or to the bridge/tier report format,
is the trigger to spin up this scanner twin and test the round trip before promoting.** Call this out
in the docs on both sides.

---

## 6. Operating model (don't run the twin 24/7)

A permanent second scanner doubles data-vendor API calls (yfinance rate limits) and CPU for no
benefit. **Spin the scanner twin up only while testing scanner changes or an interface change, then
stop it.** CC staging can run longer for Tony-side soaks; the scanner twin is on-demand.

---

## 7. Safety checklist (state-and-confirm before any VM action)

- [ ] Dev branch on the scanner repo — never its deploy branch.
- [ ] `setup_staging.sh` never writes into `/opt/trading-bot`, never edits the prod
      `.env`/config, never restarts the production scanner services (`tradingbot-api`/`-web`).
- [ ] Every scanner output path repointed at **staging-CC**, verified by reading the scanner code
      (no production reports-dir left as a default).
- [ ] Second Alpaca paper account (or confirmed read-only) — staging never touches the live $1M book.
- [ ] All scanner alerts/posting off in staging.
- [ ] Plan-First: state problem + approach + risks and get approval before writing code (CC `CLAUDE.md`
      rule; assume the same on the scanner repo).
- [ ] Both production services confirmed undisturbed after setup (`systemctl status` green, prod
      dashboard `:8765` normal, bot still dropping reports).

---

## 8. First moves for the new session

1. Read `scripts/setup_staging.sh`, `scripts/promote_staging.sh`, `docs/DEVELOPMENT.md` in the CC checkout.
2. In the scanner repo: find its launcher, systemd unit name, requirements, and **every config var
   for its output/reports dir and for reading Tony's verdicts**. Produce that list first.
3. Map each scanner output var → the matching staging-CC path (§4.2).
4. Present the plan (problem / approach / risks) and wait for approval.
5. Build `setup_staging.sh` + `promote_staging.sh` + docs on the scanner dev branch, mirroring CC.
6. Do NOT run anything on the VM without explicit go-ahead; the scripts are hand-run after market
   close, like CC's.

**Context:** $1M Alpaca **paper** account, ~90 positions, both services healthy on the VM right now.
The whole point is to never disturb that. CC staging is done; this closes the other half of the tandem.
