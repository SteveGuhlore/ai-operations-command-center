# Handoff — Tony protection, sizing, and bot→CC handoff fixes (2026-06-09)

## Context
Started from "why are Tony's entries different sizes ($1k vs $10k)?" and uncovered a
chain of deeper issues: most of the paper book was unprotected (no stop legs), the
protection reconciler was actively *de-protecting* positions, sizing was inconsistent,
positions re-entered immediately after exit, and the bot→CC brief handoff had silently
stopped. All paper (`paper-api.alpaca.markets`) — no real money — but it broke
head-to-head integrity. This session diagnosed and fixed all of it, live, during the
6/9 session.

Two accounts:
- **Tony / CC** = `/opt/command-center`, account `#PA30334APT6O` (~$1M), service `cc-runner`.
- **Bot** = `/opt/trading-bot`, account `#PA3P0RN75VL1` (~$100k), `tradingbot-*` services.
  Separate repo (on branch `feat/kinetic-dashboard`); NOT in this fix's scope.

## Root cause (the big one)
`alpaca_paper._Broker.open_orders()` queried `status=ALL, limit=500` — the 500
most-recent orders across *all* history. After churn, the actual live OCOs (days old)
fell outside that window, so the code could see neither a position's stop (→ looked
naked → protect churn) nor the order to cancel (→ cancel/replace failed `40310000`
forever). Fix: query `status=OPEN` + `nested=True` (surfaces held stop legs). This
single change fixed both the false-naked detection and the cancel/replace race.

## Code changes shipped to `master` (all deployed to the VM)
| commit | change |
|---|---|
| `aa6f9c2` | `plan_orders` skips `open` verdicts with no stop (no more naked flat-$1k entries) |
| `b70bad2` | Same-session re-entry block: a symbol exited today (any sell fill) can't be re-opened until next day (`symbols_exited_today`) |
| `95f0783` | `open_orders` uses `nested=True` + `_flatten_orders` to surface held OCO stop legs |
| `5f09384` | Review fixes: recurse past terminal (filled-bracket) parents so live legs survive; revert parent_id cancel-filter |
| `ea21857` | **`open_orders` → `status=OPEN`** (the real fix — see root cause) |
| `28fcd55` | Fixed-notional entry sizing: every buy ~`ENTRY_NOTIONAL` ($10k = 1% of $1M), `entry_qty(price, mult)`; replaces risk-based sizing for entries |

Tests: `tests/runner/test_tony_conviction_sizing.py` (22 passing) cover the cooldown,
naked-skip, nested-leg flatten, terminal-parent legs, and fixed-notional sizing.

## VM-only operational changes (NOT in git — re-apply if the VM is rebuilt)
- `/opt/command-center/.env`: **`TONY_MAX_OPEN_POSITIONS=90`** (raised 50→75→90; 1% each → ~90% deployed, 10% buffer).
- `/opt/trading-bot/config/default_config.yaml`: **`command_center_dir: /opt/command-center`**
  (was a leftover Windows path `C:/Users/alexa/Downloads/...` that dumped the bot's CC
  pushes into a junk dir; junk dir `rm`'d). This is what restored the bridge handoff.
- One-time: removed stale `2026-06-09/daily_brief` key from
  `workspace/logs/tony-bridge-processed.json` so the fresh bridge re-spawned today's brief.

## Current state (verified 6/9)
- Both books **0 naked** — every position has a working stop. Churn/`40310000` spam gone.
- New entries uniform **~$10k**; legacy off-size positions left to exit on their stops/targets.
- **Re-entry cooldown** live (observed blocking `LRCX` re-buy).
- Bot→CC handoff working: `TONY-DAILY-BRIEF-20260609` + per-ticker fan-out spawned and
  completed; intraday slots (10:30/1:00/3:30/EOD) flow as the bot drops slot files.
- Caught a real, correct behavior along the way: a batch of `close`s at the open were
  Tony's exits from 6/8 that had been *failing* due to the close bug — our fix unblocked them.

## Open punch-list (next session)
1. **Rotate the Telegram bot token** — it was printed in full in cc-runner 429 logs (and chat). Update `.env`.
2. **`bot_equity … Connection refused`** — CC can't reach the bot's local API for the head-to-head equity panel. Check `tradingbot-api` port vs what CC expects. Cosmetic.
3. **Port the `status=OPEN` fix to the bot** (`/opt/trading-bot`) — same reconciler bug; its 0-naked is currently fragile (only fits the 500-window because churn was cleared). Needs that repo added to scope.
4. **Durable brief re-trigger** — the pure-date `{date}/daily_brief` key is one-per-day; if the bridge file is overwritten after the key is set, it won't re-spawn (today's stuck-key cause). Optionally re-trigger on content change (hash/mtime).
5. **Windows-path cleanups in CC** — `GOOGLE_APPLICATION_CREDENTIALS=C:/Users/...` in `.env:113` and a `sys.path.insert` in `scripts/_runner_loop.py` (both currently harmless).

## How to verify (read-only)
- **Naked audit** (both accounts, nested-aware): see the `full_audit.py` pattern used in
  this session — for each account, a position is protected iff any open order or nested
  leg for its symbol is a sell with a stop. Expect `naked=0`.
- **Sizing**: positions opened today should show ~$10k cost basis (`qty * avg_entry`).
- **Handoff**: `ls /opt/command-center/bridge/tony-stocks/` for today's `.md` (+ slot files),
  and `journalctl -u cc-runner | grep tony_bridge` for "created daily brief / intraday".
- **Caps live**: `cat /proc/$(systemctl show -p MainPID --value cc-runner)/environ | tr '\0' '\n' | grep TONY_`.
