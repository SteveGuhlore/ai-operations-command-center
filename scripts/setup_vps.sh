#!/usr/bin/env bash
# One-time VPS setup — run as ubuntu on Hetzner CX22 (Ubuntu 22.04)
set -euo pipefail

echo "=== Updating system ==="
sudo apt-get update -qq && sudo apt-get upgrade -y -qq

echo "=== Installing Python 3.11, git, pip ==="
sudo apt-get install -y python3.11 python3.11-venv python3-pip git -qq

echo "=== Installing Claude Code ==="
curl -fsSL https://claude.ai/install.sh | sh

echo "=== Done. Clone your project next. ==="
