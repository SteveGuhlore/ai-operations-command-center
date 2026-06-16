# Debugging & testing the Tony stack

One harness, five layers. Run the harness after any change; reach for the per-surface sections
when something's red.

## The one-command harness
```bash
bash /opt/command-center/scripts/selftest.sh             # fast: deploy state, services, dashboards, live smokes, unit suites
bash /opt/command-center/scripts/selftest.sh --telegram  # also sends a real Telegram ping
bash /opt/command-center/scripts/selftest.sh --full      # also runs stress + tandem e2e (slow; after close)
```
Prints `✅ ALL GREEN` / `❌` with a pass/fail count; exit 0 = healthy. Safe to run during market hours
without `--full`.

## The five layers
| Layer | Command | Covers |
|---|---|---|
| Unit | `.venv/bin/python -m pytest tests/...` | per-module logic |
| Integration / stress | `pytest tests/runner/test_stress_*` · `full_e2e_sync_test.py --quick` | backend system + bot↔CC tandem |
| Live smoke | `selftest.sh` | the running services |
| Error console | browser `?debug=1` | frontend JS errors |
| Deploy-via-Action | GitHub → Actions → "Deploy to VM" | push-to-VM (needs the runner) |

---

## Deploy (push → VM) via the self-hosted runner
The runner lives on the VM; a workflow run executes the deploy there and the result is read back
through GitHub — no SSH. Install once (see `docs/DEPLOY.md` → "self-hosted runner"). Then:
- **Trigger:** GitHub → repo → Actions → **Deploy to VM** → Run workflow (`mode: deploy` or `verify-only`),
  or programmatically (`actions_run_trigger`).
- **Debug a run:** Actions → the run → open the `deploy` job logs. `verify-only` prints service
  status + the live `/api/command-center` agreement + the readiness sweep without changing code.
- **Health of the runner itself:** on the VM, `sudo ~/actions-runner/svc.sh status` (want `active`).

## Telegram
- **Throttle (no send):** covered by `selftest.sh`; or `pytest tests/runner/test_notify_policy.py`.
- **Real ping:** `bash scripts/selftest.sh --telegram` (pulls the live token from cc-runner).
- **Tuning:** `TONY_REPRICE_COOLDOWN_MIN` (default 90), `TONY_REPRICE_MIN_MOVE_PCT` (default 0.75),
  `TONY_NOTIFY_POLICY=off` (kill-switch → legacy ping-every-move).
- **EOD timing:** end-of-day messages fire only after the close (`market_clock.is_after_close`).
  To force a re-fire after fixing state: `rm workspace/nudge-state.json workspace/notify-daily-state.json`.

## Error / debug console (frontend)
The console is part of each dashboard page and is **off by default**. You open it *with* the
dashboard:
1. Append `?debug=1` to the dashboard URL (persists via localStorage; `?debug=0` turns it off).
2. Trigger a test error in the browser devtools console:
   `setTimeout(() => { throw new Error("debug console test"); })`
   …or an unhandled rejection: `Promise.reject(new Error("rejection test"))`.
3. The overlay auto-opens with the message, file, line, stack, and a **Copy Errors** button — paste
   that straight back to whoever's debugging.
- **Bot scanner** (Next/React, `:3000`): also catches React render errors via the error boundary.
- **CC command-center** (static, `:8765`): catches `window` errors + unhandled rejections.
- Real-world use: leave `?debug=1` on while reproducing a "blank panel / stuck loading" and the
  actual runtime error surfaces instead of failing silently.

## Scorecard / outcomes / verdict memory
```bash
cd /opt/command-center
.venv/bin/python -c "from runner.ledger.tony_scorecard import compute_record as r; x=r(); print(x['status'], x['graded'], x['agreement'])"
ls -la workspace/tony-verdicts-archive.json* workspace/tony-graded-archive.json   # .bak = corruption recovery; graded = monotonic lock
python3 -c "import json,collections;v=json.load(open('/opt/trading-bot/reports/tony_stocks_verdicts.json'));print(len(v),'live verdicts; dates:',dict(collections.Counter(x.get('date') for x in v)))"
```
The agreement total should only ever grow. A `.corrupt` sibling next to the archive means it
recovered from backup — investigate the cause but no data was lost.

## Stress + tandem (after close)
```bash
cd /opt/command-center && .venv/bin/python -m pytest tests/runner/test_stress_round2.py tests/runner/test_stress_integration.py -q
cd /opt/trading-bot   && PYTHONPATH=src .venv/bin/python scripts/full_e2e_sync_test.py --quick
```
These exercise the backend (runner concurrency, reaper, bot↔CC sync) — a different layer than the
browser error console. `selftest.sh --full` runs both for you.
