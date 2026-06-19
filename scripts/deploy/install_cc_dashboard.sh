#!/usr/bin/env bash
# install_cc_dashboard.sh — split the always-on dashboard away from the agent loop.
#
# WHY: cc-runner runs ONE process (scripts/launch.py) that is BOTH the dashboard
# (uvicorn dashboard.server:app on :8765, which also backs Tony at :8444) AND the
# agent cron loop (run_cycle -> LLM calls = $). So stopping the agents to save money
# also dropped the dashboard. This installs a dedicated, agent-free dashboard service
# that stays up with ZERO model spend (it only reads Alpaca + the local ledgers), and
# parks cc-runner (the spend) stopped + disabled until you want agents back.
#
# After this:
#   cc-dashboard.service  -> always-on UI on :8765  (no LLM, no spend)   [enabled]
#   cc-runner.service     -> agent loop only         (LLM spend)         [stopped+disabled]
#
# Re-enable agents later WITHOUT touching the dashboard (no :8765 fight — a drop-in
# adds --no-dashboard to cc-runner so it runs the loop only):
#   sudo systemctl enable --now cc-runner
# Pause agents again (dashboard stays up):
#   sudo systemctl disable --now cc-runner
#
# Idempotent. Run on the VM as the user that owns /opt/command-center (or with sudo):
#   bash /opt/command-center/scripts/deploy/install_cc_dashboard.sh
set -uo pipefail

CC_DIR="${CC_DIR:-/opt/command-center}"
PORT="${CC_PORT:-8765}"
PY="$CC_DIR/.venv/bin/python"
UNIT="/etc/systemd/system/cc-dashboard.service"
RUNNER_DROPIN_DIR="/etc/systemd/system/cc-runner.service.d"

# Run privileged steps via sudo unless we're already root.
SUDO=""; [ "$(id -u)" -eq 0 ] || SUDO="sudo"

# --- preflight -------------------------------------------------------------
[ -d "$CC_DIR" ]  || { echo "FATAL: $CC_DIR not found (override with CC_DIR=...)"; exit 1; }
[ -x "$PY" ]      || { echo "FATAL: venv python missing at $PY"; exit 1; }
# Run the import from INSIDE $CC_DIR so the `dashboard` package resolves — the service does
# this via WorkingDirectory, so mirror it here. Surface the real traceback if it still fails.
if ! ( cd "$CC_DIR" && "$PY" -c 'import uvicorn, dashboard.server' ) 2>/tmp/cc_dash_import.err; then
  echo "FATAL: 'uvicorn dashboard.server' not importable under the venv. Error:"
  sed 's/^/    /' /tmp/cc_dash_import.err 2>/dev/null
  echo "  (venv python: $PY ; import cwd: $CC_DIR)"
  exit 1
fi

# Own the service with the account that owns the checkout (NOT root, even under sudo),
# so load_dotenv() reads that user's /opt/command-center/.env exactly like cc-runner does.
RUN_USER="$(stat -c '%U' "$CC_DIR" 2>/dev/null || true)"
[ -z "$RUN_USER" -o "$RUN_USER" = "root" ] && RUN_USER="${SUDO_USER:-$RUN_USER}"
[ -n "$RUN_USER" ] || { echo "FATAL: could not determine an owner for $CC_DIR"; exit 1; }
echo "Dashboard service will run as: $RUN_USER   (cwd $CC_DIR, port $PORT)"

# --- 1) write the always-on, agent-free dashboard unit ---------------------
# No EnvironmentFile on purpose: dashboard/server.py calls load_dotenv() and, with
# WorkingDirectory=$CC_DIR, picks up $CC_DIR/.env — the same way launch.py does. That
# avoids systemd-vs-dotenv parsing differences breaking startup. Restart=always so the
# UI self-heals; this process makes NO model calls, so it never costs anything to keep up.
echo "[1/5] writing $UNIT"
$SUDO tee "$UNIT" >/dev/null <<EOF
# cc-dashboard.service — Command Center dashboard ONLY (no agent loop, no LLM spend).
# Serves the CC dashboard + Tony (/tony, /api/tony/*) on 127.0.0.1:$PORT.
# Installed by scripts/deploy/install_cc_dashboard.sh. Safe to keep running 24/7.
[Unit]
Description=Command Center Dashboard (UI only, no agents)
After=network-online.target
Wants=network-online.target
ConditionPathExists=$PY

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$CC_DIR
ExecStart=$PY -m uvicorn dashboard.server:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# --- 2) park the agent loop: drop-in so a future start is dashboard-free ----
# cc-runner's launcher starts a dashboard by default and would EXIT on the :8765
# clash (its _already_running guard). This drop-in re-points ExecStart at the SAME
# command plus --no-dashboard, so when you re-enable cc-runner it runs the agent loop
# only and leaves cc-dashboard's port alone. We DON'T start it here — agents stay off.
if systemctl cat cc-runner >/dev/null 2>&1; then
  CUR_EXEC="$(systemctl cat cc-runner 2>/dev/null | grep -m1 '^ExecStart=' || true)"
  if [ -n "$CUR_EXEC" ] && ! printf '%s' "$CUR_EXEC" | grep -q -- '--no-dashboard'; then
    echo "[2/5] adding --no-dashboard drop-in for cc-runner (agents-only when re-enabled)"
    $SUDO mkdir -p "$RUNNER_DROPIN_DIR"
    # Clear then redefine ExecStart (systemd requires the reset for list-valued keys).
    $SUDO tee "$RUNNER_DROPIN_DIR/10-no-dashboard.conf" >/dev/null <<EOF
[Service]
ExecStart=
$CUR_EXEC --no-dashboard
EOF
  else
    echo "[2/5] cc-runner already agent-only (or no ExecStart found) — leaving drop-in as-is"
  fi
else
  echo "[2/5] cc-runner.service not present — skipping drop-in (nothing to park)"
fi

# --- 3) stop + disable the agent loop (this is what halts the spend) --------
echo "[3/5] stopping + disabling cc-runner (halts agent/LLM spend; dashboard takes over :$PORT)"
$SUDO systemctl disable --now cc-runner 2>/dev/null || echo "  (cc-runner was not active — fine)"

# --- 4) install + start the dashboard --------------------------------------
echo "[4/5] enabling + starting cc-dashboard"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now cc-dashboard

# --- 5) verify -------------------------------------------------------------
echo "[5/5] verifying…"
sleep 3
active="$($SUDO systemctl is-active cc-dashboard 2>/dev/null || true)"
echo "  cc-dashboard is-active: ${active:-unknown}"
ok=0
if curl -fs "http://127.0.0.1:$PORT/api/tony/live" 2>/dev/null | grep -q '"status"'; then
  echo "  OK — /api/tony/live answers (live data path is up)."
  ok=1
else
  echo "  WARN — /api/tony/live did not answer yet; check: journalctl -u cc-dashboard -n 50 --no-pager"
fi
curl -fs "http://127.0.0.1:$PORT/tony" 2>/dev/null | grep -qi '<' \
  && echo "  OK — /tony HTML serves." \
  || echo "  WARN — /tony HTML did not serve yet."

cat <<EOF

============================================================
 DONE — dashboard is now decoupled from the agents.
============================================================
  Dashboard (always on, no spend):  http://127.0.0.1:$PORT
      CC:    http://127.0.0.1:$PORT/
      Tony:  http://127.0.0.1:$PORT/tony   (tailnet :8444/tony via serve_tony.sh)
  Status / logs:
      systemctl status cc-dashboard
      journalctl -u cc-dashboard -f

  Agents are OFF (cc-runner stopped + disabled) — zero model spend.
  Turn agents back ON later (dashboard stays up, runs agent-only):
      sudo systemctl enable --now cc-runner
  Pause agents again:
      sudo systemctl disable --now cc-runner
EOF
[ "$ok" -eq 1 ] || echo "NOTE: verify warned above — confirm before trusting the UI."
