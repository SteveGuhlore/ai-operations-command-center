#!/usr/bin/env bash
# serve_tony.sh — give Tony's standalone dashboard its own Tailscale address.
#
# Tony runs INSIDE the command-center FastAPI app (127.0.0.1:8765) at /tony, with his data
# under /api/*. This proxies a dedicated tailnet HTTPS port (default 8444, mirroring the
# scanner's 8443) to the WHOLE CC app, so on any device with Tailscale on:
#
#       Tony's home:   https://<this-node>.<your-tailnet>.ts.net:8444/tony
#       his data:      https://<this-node>.<your-tailnet>.ts.net:8444/api/...
#
# WHY whole-app and not a clean "/" -> /tony root: `tailscale serve` APPENDS the request path
# to the target, so a subpath target (…/tony) double-prefixes ("/tony/tony") and 404s. Proxying
# the whole app keeps every /api call resolving; Tony just lives at /tony on the port.
#
# No code change, no extra service — Tony stays in the CC process; this is only routing, and the
# tailscale serve config persists across restarts. Run on the VM as the tailscale-authed user.
#
#   bash scripts/deploy/serve_tony.sh            # set it up on :8444
#   bash scripts/deploy/serve_tony.sh 8500       # use a different port
#   bash scripts/deploy/serve_tony.sh --status   # show the current tailscale serve config
#   bash scripts/deploy/serve_tony.sh --off      # tear the :8444 mapping down
set -uo pipefail

CC="http://127.0.0.1:8765"
ARG="${1:-}"

case "$ARG" in
  --status) exec tailscale serve status ;;
  --off)
    tailscale serve --https=8444 off 2>/dev/null || true
    echo "Removed the :8444 mapping (if it existed)."
    exit 0 ;;
esac

PORT="${ARG:-8444}"
[[ "$PORT" =~ ^[0-9]+$ ]] || { echo "usage: serve_tony.sh [PORT|--status|--off]"; exit 1; }
command -v tailscale >/dev/null 2>&1 || { echo "tailscale not found on PATH"; exit 1; }

# Reset any prior mapping on this port (e.g. an earlier clean-root attempt that double-prefixed),
# then proxy the whole CC app. Idempotent — safe to re-run on every deploy.
tailscale serve --https="$PORT" off 2>/dev/null || true
tailscale serve --bg --https="$PORT" "$CC"

# Resolve this node's MagicDNS name for a friendly URL (json first, then plain hostname).
host="$(tailscale status --json 2>/dev/null \
        | python3 -c 'import json,sys;print(json.load(sys.stdin).get("Self",{}).get("DNSName","").rstrip("."))' 2>/dev/null || true)"
[ -z "${host:-}" ] && host="$(hostname -f 2>/dev/null || hostname)"
url="https://${host}:${PORT}/tony"

echo
echo "Tony's standalone home:  $url"
echo "Verifying the CC app on 127.0.0.1:8765 …"
if curl -fs "$CC/api/tony/live" 2>/dev/null | grep -q '"status"'; then
  echo "  OK — Tony's data route answers. Open  $url  on a device with Tailscale on."
else
  echo "  WARN — the CC app didn't answer on 127.0.0.1:8765. Is cc-runner up?  (sudo systemctl status cc-runner)"
fi
echo "  Review: tailscale serve status   |   Remove: bash $0 --off"
