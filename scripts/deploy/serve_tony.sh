#!/usr/bin/env bash
# serve_tony.sh — give Tony's standalone dashboard its OWN Tailscale address.
#
# Tony runs INSIDE the command-center FastAPI app (127.0.0.1:8765) at /tony, with his data
# under /api/*. This maps a dedicated tailnet HTTPS port (default 8444, mirroring the scanner's
# 8443) so Tony has his own clean home at:
#
#       https://<this-node>.<your-tailnet>.ts.net:8444/
#
# …while his /api/* calls still resolve. Run ONCE on the VM, as the tailscale-authed user.
# No code change and no extra service — Tony stays in the CC process; this is just routing.
#
#   bash scripts/deploy/serve_tony.sh            # set it up on :8444
#   bash scripts/deploy/serve_tony.sh 8500       # use a different port
#   bash scripts/deploy/serve_tony.sh --status   # show the current tailscale serve config
#   bash scripts/deploy/serve_tony.sh --off      # tear the :8444 mapping down
#
# NOTE: `tailscale serve` flags vary a little by version. If the clean-root mapping below
# errors or doesn't verify, use the bulletproof fallback it prints (whole app on the port,
# Tony then at  …:8444/tony ).
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

echo "Mapping  https :$PORT  ->  $CC   (/ = Tony's page, /api = his data)"
# Clean-root: '/' serves the Tony page, '/api' serves the data routes. More-specific path wins.
tailscale serve --bg --https="$PORT" --set-path=/api "$CC/api"
tailscale serve --bg --https="$PORT" --set-path=/    "$CC/tony"

# Resolve this node's MagicDNS name for a friendly URL.
host="$(tailscale status --json 2>/dev/null | grep -o '"DNSName":"[^"]*"' | head -1 | cut -d'"' -f4 | sed 's/\.$//')"
url="https://${host:-<this-node>}:${PORT}"
echo
echo "Tony's standalone home:  $url"
echo "Verifying his data route…"
if curl -fsk "$url/api/tony/live" 2>/dev/null | grep -q '"status"'; then
  echo "  OK — $url is live."
else
  echo "  WARN — the clean-root mapping didn't verify on this tailscale version. Fallback:"
  echo "    tailscale serve --https=$PORT off"
  echo "    tailscale serve --bg --https=$PORT $CC     # then open  $url/tony"
fi
