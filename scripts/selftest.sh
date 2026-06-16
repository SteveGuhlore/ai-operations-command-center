#!/usr/bin/env bash
# selftest.sh — one-command health + integration check for the Tony stack (bot + command-center).
#
#   bash scripts/selftest.sh              # fast, read-only + unit suites (safe anytime)
#   bash scripts/selftest.sh --telegram   # also send a real Telegram ping (pulls live token)
#   bash scripts/selftest.sh --full       # also run stress + tandem e2e (slow; prefer after close)
#
# Exit 0 = all green. Each check is independent (no set -e) so one red never hides the rest.
set -uo pipefail

BOT_DIR="${BOT_DIR:-/opt/trading-bot}"
CC_DIR="${CC_DIR:-/opt/command-center}"
PASS=0
FAIL=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; PASS=$((PASS + 1)); }
bad()  { printf '  \033[31m✗ %s\033[0m\n' "$1"; FAIL=$((FAIL + 1)); }
note() { printf '    %s\n' "$1"; }
line() { printf '\n== %s ==\n' "$1"; }

DO_FULL=0; DO_TG=0
for a in "$@"; do case "$a" in --full) DO_FULL=1 ;; --telegram) DO_TG=1 ;; esac; done

line "DEPLOY STATE (VM vs origin)"
for pair in "$BOT_DIR:main" "$CC_DIR:master"; do
  dir="${pair%:*}"; br="${pair##*:}"; name="$(basename "$dir")"
  git -C "$dir" fetch -q origin "$br" 2>/dev/null
  l="$(git -C "$dir" rev-parse --short HEAD 2>/dev/null)"
  r="$(git -C "$dir" rev-parse --short "origin/$br" 2>/dev/null)"
  [ -n "$l" ] && [ "$l" = "$r" ] && ok "$name @ $l == origin/$br" || bad "$name @ ${l:-?} != origin/$br (${r:-?}) — pull needed"
done

line "SERVICES"
for s in tradingbot-api tradingbot-offhours tradingbot-watch cc-runner tradingbot-web; do
  st="$(systemctl is-active "$s" 2>/dev/null || echo inactive)"
  [ "$st" = active ] && ok "$s active" || bad "$s $st"
done

line "DASHBOARDS / API (HTTP)"
http() { c="$(curl -s -o /dev/null -m 8 -w '%{http_code}' "$2" 2>/dev/null)"; [ "$c" = "$3" ] && ok "$1 -> $c" || bad "$1 -> ${c:-no-response} (want $3)"; }
http "CC command-center :8765" http://127.0.0.1:8765/ 200
http "bot scanner :3000"       http://127.0.0.1:3000/ 200
http "bot api :8001 /api/command-center" http://127.0.0.1:8001/api/command-center 200

line "SCORECARD / MEMORY (live)"
( cd "$CC_DIR" && .venv/bin/python - <<'PY'
import sys
from runner.ledger.tony_scorecard import compute_record
r = compute_record()
print("    status=%s graded=%s agreement=%s" % (r.get("status"), r.get("graded"), r.get("agreement")))
sys.exit(0 if r.get("status") == "scored" and (r.get("graded") or 0) > 0 else 1)
PY
) && ok "compute_record is scored with graded picks" || bad "compute_record not scored (no graded picks)"
[ -f "$CC_DIR/workspace/tony-verdicts-archive.json" ] && ok "verdict archive present" || bad "verdict archive MISSING"
[ -f "$CC_DIR/workspace/tony-verdicts-archive.json.bak" ] && ok "verdict archive .bak present" || note "(.bak appears after the next pre-open archive — informational)"
[ -f "$CC_DIR/workspace/tony-graded-archive.json" ] && ok "graded archive present (monotonic lock)" || note "(graded archive appears after the next write_record — informational)"

line "TELEGRAM throttle (pure logic, no send)"
( cd "$CC_DIR" && .venv/bin/python - <<'PY'
import sys, tempfile, pathlib
from runner.tools import notify_policy as p
p.STATE_FILE = pathlib.Path(tempfile.mkdtemp()) / "s.json"        # isolate — no live-state pollution
first = p.gate_reprice("ZZZTEST", 10.0, 12.0)
dup   = p.gate_reprice("ZZZTEST", 10.0, 12.0)
lock  = p.gate_reprice("ZZZTEST", 10.5, 12.0, entry=10.0)         # stop crosses entry -> lock
sys.exit(0 if first["send"] and not dup["send"] and lock["lock"] else 1)
PY
) && ok "reprice dedup + breakeven-lock work" || bad "reprice throttle FAILED"

if [ "$DO_TG" = 1 ]; then
  line "TELEGRAM send (real ping)"
  PID="$(systemctl show -p MainPID --value cc-runner 2>/dev/null)"
  if [ -n "${PID:-}" ] && sudo test -r "/proc/$PID/environ" 2>/dev/null; then
    sudo cat "/proc/$PID/environ" | tr '\0' '\n' | grep -E '^TELEGRAM_|^TONY_NOTIFY' > /tmp/_tg.env
    set -a; . /tmp/_tg.env; set +a; rm -f /tmp/_tg.env
    ( cd "$CC_DIR" && .venv/bin/python -c "import sys; from runner.tools.notify import notify; r=notify('🔧 selftest ping — ignore'); print('   ',r); sys.exit(0 if r.get('sent') else 1)" ) \
      && ok "telegram ping delivered" || bad "telegram ping failed (check token/chat env)"
  else
    bad "couldn't read cc-runner env for the ping (run with sudo)"
  fi
fi

line "UNIT SUITES"
( cd "$CC_DIR" && .venv/bin/python -m pytest -q \
    tests/runner/test_tony_scorecard.py tests/runner/test_verdict_archive.py \
    tests/runner/test_notify_policy.py tests/runner/test_market_clock.py >/tmp/_ut.log 2>&1 ) \
  && ok "CC unit suites pass" || { bad "CC unit suites FAILED"; tail -6 /tmp/_ut.log | sed 's/^/    /'; }

if [ "$DO_FULL" = 1 ]; then
  line "STRESS + TANDEM E2E (slow)"
  ( cd "$CC_DIR" && .venv/bin/python -m pytest -q \
      tests/runner/test_stress_round2.py tests/runner/test_stress_integration.py >/tmp/_st.log 2>&1 ) \
    && ok "stress suites pass" || { bad "stress FAILED"; tail -6 /tmp/_st.log | sed 's/^/    /'; }
  ( cd "$BOT_DIR" && PYTHONPATH=src .venv/bin/python scripts/full_e2e_sync_test.py --quick >/tmp/_tan.log 2>&1 ) \
    && ok "tandem bot<->CC e2e --quick pass" || { bad "tandem e2e FAILED"; tail -8 /tmp/_tan.log | sed 's/^/    /'; }
fi

line "SUMMARY"
printf 'Tony stack self-test: \033[32m%d passed\033[0m, \033[31m%d failed\033[0m\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && { echo "✅ ALL GREEN"; exit 0; } || { echo "❌ see failures above"; exit 1; }
