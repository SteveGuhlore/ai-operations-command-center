# Agentic OS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the AI Operations Command Center to a Hetzner VPS running 24/7, with an Obsidian vault for agent memory and a nightly OpenClaw improvement loop that rewrites agent prompts based on real output data.

**Architecture:** Two autonomous loops share a git-synced vault on a single Linux VPS. The execution loop (existing Python runner) writes session summaries to `/vault/sessions/` after every task. The improvement loop (nightly Python script via Claude API) reads those summaries and rewrites `agents/*.md` files, then commits. A FastAPI dashboard with new endpoints exposes loop status and one-click pod triggers, served publicly via Cloudflare Tunnel.

**Tech Stack:** Python 3.11, FastAPI, Anthropic SDK, systemd, Ubuntu 22.04, Hetzner CX22, Cloudflare Tunnel, GitHub (vault repo), Obsidian (local viewer)

**Spec:** `docs/superpowers/specs/2026-05-22-agentic-os-design.md`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `runner/tools/vault_writer.py` | Writes per-task session summary to `/vault/sessions/YYYY-MM-DD/` |
| Create | `scripts/vault_sync.sh` | Git-pushes vault repo to GitHub after each execution batch (Linux only) |
| Create | `scripts/improvement_loop.py` | Nightly job: reads vault, calls Claude API, rewrites `agents/*.md`, commits |
| Create | `scripts/setup_vps.sh` | One-time VPS provisioning script (copy-paste on server) |
| Create | `scripts/systemd/execution-loop.service` | systemd service for Python runner |
| Create | `scripts/systemd/improvement-loop.service` | systemd one-shot service for nightly job |
| Create | `scripts/systemd/improvement-loop.timer` | systemd timer — fires at 2 AM daily |
| Create | `vault/AGENTS.md` | OpenClaw workspace injection: agent roster |
| Create | `vault/SOUL.md` | OpenClaw workspace injection: brand voice + values |
| Create | `vault/TOOLS.md` | OpenClaw workspace injection: available tools |
| Create | `vault/.gitignore` | Track all vault files |
| Create | `tests/runner/test_vault_writer.py` | Unit tests for vault writer |
| Create | `tests/runner/test_improvement_loop.py` | Unit tests for improvement loop parsing |
| Modify | `runner/main.py` | Call `write_vault_session()` after each task; call `_sync_vault()` after each cycle |
| Modify | `dashboard/server.py` | Add `/api/status`, `/api/trigger`, `/api/vault/feed` endpoints |
| Modify | `dashboard/index.html` | Add loop status row, trigger buttons section, vault feed panel |

---

## Phase 1 — VPS + Execution Loop

### Task 1: Create vault_writer.py

**Files:**
- Create: `runner/tools/vault_writer.py`
- Create: `tests/runner/test_vault_writer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runner/test_vault_writer.py
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


def test_write_vault_session_creates_file(tmp_path):
    with patch("runner.tools.vault_writer.VAULT_DIR", tmp_path):
        import importlib
        import runner.tools.vault_writer as vw
        importlib.reload(vw)
        vw.write_vault_session(
            "TEST-001",
            "social_media_worker",
            {
                "output": "produced a great video script",
                "cost_usd": 0.0012,
                "input_tokens": 200,
                "output_tokens": 80,
            },
        )
    today = datetime.now().strftime("%Y-%m-%d")
    path = tmp_path / "sessions" / today / "TEST-001.md"
    assert path.exists(), "session file not created"
    content = path.read_text()
    assert "TEST-001" in content
    assert "social_media_worker" in content
    assert "done" in content
    assert "$0.0012" in content


def test_write_vault_session_marks_failed_on_error(tmp_path):
    with patch("runner.tools.vault_writer.VAULT_DIR", tmp_path):
        import importlib
        import runner.tools.vault_writer as vw
        importlib.reload(vw)
        vw.write_vault_session(
            "TEST-002",
            "debug_worker",
            {"error": "API timeout after 30s", "task_id": "TEST-002"},
        )
    today = datetime.now().strftime("%Y-%m-%d")
    content = (tmp_path / "sessions" / today / "TEST-002.md").read_text()
    assert "failed" in content
    assert "API timeout after 30s" in content


def test_write_vault_session_truncates_long_output(tmp_path):
    with patch("runner.tools.vault_writer.VAULT_DIR", tmp_path):
        import importlib
        import runner.tools.vault_writer as vw
        importlib.reload(vw)
        vw.write_vault_session(
            "TEST-003",
            "content_worker",
            {"output": "x" * 2000, "cost_usd": 0.001, "input_tokens": 100, "output_tokens": 400},
        )
    today = datetime.now().strftime("%Y-%m-%d")
    content = (tmp_path / "sessions" / today / "TEST-003.md").read_text()
    assert len(content) < 3000, "output not truncated"
```

- [ ] **Step 2: Run tests — expect ImportError (module doesn't exist yet)**

```
python -m pytest tests/runner/test_vault_writer.py -v
```

Expected: `ModuleNotFoundError: No module named 'runner.tools.vault_writer'`

- [ ] **Step 3: Create vault_writer.py**

```python
# runner/tools/vault_writer.py
from datetime import datetime
from pathlib import Path

VAULT_DIR = Path(__file__).parent.parent.parent / "vault"

_OUTPUT_PREVIEW_CHARS = 500


def write_vault_session(task_id: str, role_id: str, result: dict) -> None:
    """Write a session summary for one completed task into the Obsidian vault."""
    today = datetime.now().strftime("%Y-%m-%d")
    session_dir = VAULT_DIR / "sessions" / today
    session_dir.mkdir(parents=True, exist_ok=True)

    status = "failed" if "error" in result else "done"
    output_preview = str(result.get("output", ""))[:_OUTPUT_PREVIEW_CHARS]

    content = (
        f"# {task_id} — {role_id}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Status: {status}\n"
        f"Tokens: {result.get('input_tokens', 0)} input / {result.get('output_tokens', 0)} output\n"
        f"Cost: ${result.get('cost_usd', 0.0):.4f}\n"
        f"Errors: {result.get('error', 'none')}\n"
        f"\n"
        f"## Output Preview\n"
        f"{output_preview}\n"
    )

    (session_dir / f"{task_id}.md").write_text(content, encoding="utf-8")
```

- [ ] **Step 4: Run tests — expect PASS**

```
python -m pytest tests/runner/test_vault_writer.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add runner/tools/vault_writer.py tests/runner/test_vault_writer.py
git commit -m "feat: vault_writer — write session summaries to /vault/sessions/"
```

---

### Task 2: Wire vault_writer into run_task() and _sync_vault into run_cycle()

**Files:**
- Modify: `runner/main.py`

- [ ] **Step 1: Add import and `_sync_vault` helper to main.py**

In `runner/main.py`, add after the existing imports (after line 24, `from runner.tools.task_creator import TOOL_SPEC as TASK_CREATOR_TOOL_SPEC`):

```python
import subprocess
import sys

from runner.tools.vault_writer import write_vault_session
```

Then add this function after the `_done_task_summary` function (after line 71):

```python
def _sync_vault() -> None:
    if sys.platform == "win32":
        return  # vault sync runs on Linux VPS only
    sync_script = Path(__file__).parent.parent / "scripts" / "vault_sync.sh"
    if not sync_script.exists():
        return
    try:
        subprocess.run(["bash", str(sync_script)], timeout=30, check=False)
    except Exception as exc:
        log.warning("vault sync skipped: %s", exc)
```

- [ ] **Step 2: Call write_vault_session in run_task() on success**

In `runner/main.py`, in the `run_task()` function, add one line after `write_task_output` (currently line 174):

```python
        write_task_output(task_id, result["output"], "in_progress")
        write_vault_session(task_id, role_id, result)          # NEW
        move_task(task_id, "in_progress", "done")
```

- [ ] **Step 3: Call write_vault_session in run_task() on failure**

In `runner/main.py`, in the `except Exception` block of `run_task()` (currently around line 181), add one line:

```python
    except Exception as exc:
        log.error("%s failed %s: %s", role_id, task_id, exc)
        write_vault_session(task_id, role_id, {"error": str(exc), "task_id": task_id})  # NEW
        try:
            move_task(task_id, "in_progress", "failed")
```

- [ ] **Step 4: Call _sync_vault at end of run_cycle()**

In `runner/main.py`, in `run_cycle()`, add one line after `_maybe_spawn_planning_task()` (currently line 216):

```python
    _maybe_spawn_planning_task()
    _sync_vault()                                              # NEW
```

- [ ] **Step 5: Verify runner still imports cleanly**

```
python -c "from runner.main import run_cycle; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add runner/main.py
git commit -m "feat: wire vault_writer and vault_sync into execution loop"
```

---

### Task 3: Provision Hetzner VPS

This task has no code — it is infrastructure setup. Follow these steps exactly.

- [ ] **Step 1: Create Hetzner account**

Go to `https://www.hetzner.com/cloud` → Sign up → Add a payment method.

- [ ] **Step 2: Create the server**

In the Hetzner Cloud Console:
- Location: pick closest to you (US East or EU)
- Image: **Ubuntu 22.04**
- Type: **CX22** (2 vCPU, 4 GB RAM — ~$4.15/month)
- SSH Key: paste your public key (`~/.ssh/id_rsa.pub` on Windows via Git Bash, or generate one with `ssh-keygen`)
- Name: `ai-ops`
- Click **Create & Buy Now**

Expected: server is created in ~30 seconds. Note the IPv4 address shown (e.g. `65.21.xxx.xxx`).

- [ ] **Step 3: Verify SSH access**

```bash
ssh ubuntu@<YOUR_VPS_IP>
```

Expected: you are logged in. If prompted about host key, type `yes`.

---

### Task 4: Deploy project to VPS

Run all commands via SSH on the VPS (`ssh ubuntu@<YOUR_VPS_IP>`).

- [ ] **Step 1: Run the one-time setup script**

On your **Windows machine**, create `scripts/setup_vps.sh` with this content:

```bash
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
```

Commit and push, then on the VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/<YOUR_GITHUB_USER>/ai-ops/master/scripts/setup_vps.sh | bash
```

Expected: system updated, Python 3.11 installed, Claude Code installed.

- [ ] **Step 2: Clone the project**

On the VPS:

```bash
cd /home/ubuntu
git clone https://github.com/<YOUR_GITHUB_USER>/<YOUR_REPO_NAME>.git ai-ops
cd ai-ops
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Expected: `Successfully installed ...` with no errors.

- [ ] **Step 3: Copy .env to VPS securely**

On your **Windows machine** (Git Bash or PowerShell with ssh):

```bash
scp .env ubuntu@<YOUR_VPS_IP>:/home/ubuntu/ai-ops/.env
```

- [ ] **Step 4: Verify the runner starts**

On the VPS:

```bash
cd /home/ubuntu/ai-ops
source venv/bin/activate
python -c "from runner.main import run_cycle; print('Runner imports OK')"
```

Expected: `Runner imports OK`

---

### Task 5: Create systemd service files

**Files:**
- Create: `scripts/systemd/execution-loop.service`
- Create: `scripts/systemd/improvement-loop.service`
- Create: `scripts/systemd/improvement-loop.timer`

- [ ] **Step 1: Create execution-loop.service**

```ini
# scripts/systemd/execution-loop.service
[Unit]
Description=ThePromptVaultUS AI Ops Execution Loop
After=network.target
Wants=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ai-ops
EnvironmentFile=/home/ubuntu/ai-ops/.env
ExecStart=/home/ubuntu/ai-ops/venv/bin/python scripts/launch.py --interval 300
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Create improvement-loop.service**

```ini
# scripts/systemd/improvement-loop.service
[Unit]
Description=ThePromptVaultUS AI Ops Improvement Loop (nightly)
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/ai-ops
EnvironmentFile=/home/ubuntu/ai-ops/.env
ExecStart=/home/ubuntu/ai-ops/venv/bin/python scripts/improvement_loop.py
StandardOutput=journal
StandardError=journal
```

- [ ] **Step 3: Create improvement-loop.timer**

```ini
# scripts/systemd/improvement-loop.timer
[Unit]
Description=AI Ops Improvement Loop — fires at 2 AM daily
Requires=improvement-loop.service

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 4: Install and enable services on VPS**

On the VPS, run these commands (one block, copy-paste):

```bash
cd /home/ubuntu/ai-ops
sudo cp scripts/systemd/execution-loop.service /etc/systemd/system/
sudo cp scripts/systemd/improvement-loop.service /etc/systemd/system/
sudo cp scripts/systemd/improvement-loop.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable execution-loop.service
sudo systemctl enable improvement-loop.timer
sudo systemctl start execution-loop.service
sudo systemctl start improvement-loop.timer
```

- [ ] **Step 5: Verify execution loop is running**

```bash
sudo systemctl status execution-loop.service
```

Expected output includes: `Active: active (running)`

- [ ] **Step 6: Verify timer is scheduled**

```bash
sudo systemctl list-timers improvement-loop.timer
```

Expected output includes a `NEXT` time of today or tomorrow at 02:00:00.

- [ ] **Step 7: Commit service files**

On your Windows machine:

```bash
git add scripts/setup_vps.sh scripts/systemd/
git commit -m "feat: systemd services for execution loop and improvement timer"
```

---

## Phase 2 — Memory Layer (Obsidian Vault)

### Task 6: Create vault directory structure and OpenClaw workspace files

**Files:**
- Create: `vault/AGENTS.md`
- Create: `vault/SOUL.md`
- Create: `vault/TOOLS.md`
- Create: `vault/.gitignore`

- [ ] **Step 1: Create vault/AGENTS.md**

```markdown
# Agent Roster — ThePromptVaultUS

## Atlas (manager)
Orchestrator. Monitors task queue. Spawns 6-8 new tasks when queue < 3.
Focus: high-ROI video production tasks for Spark.

## Spark (social_media_worker)
Full video pipeline: script → audio → images → MP4.
Target: at least 3 videos per day. Hook-first writing style. Short, punchy scripts.

## Maker (digital_product_worker)
Creates PDF prompt packs (30-50 prompts, $6-$14). Focus on AI tools for creators,
freelancers, and small business owners.

## Muse (content_worker)
Captions, written content, blog-style posts. ThePromptVaultUS voice.

## Market (marketing_worker)
Etsy listings, hooks, offer positioning. Conversion-focused copy.

## Frame (media_worker)
Standalone image generation — thumbnails, product covers, social post visuals.

## Echo (audio_worker)
Standalone voiceover and audio content generation.

## Scout (debug_worker)
Validation, research, error investigation, reporting.
```

- [ ] **Step 2: Create vault/SOUL.md**

```markdown
# ThePromptVaultUS — Brand Soul

## Mission
Make AI accessible to everyday creators, freelancers, and small business owners
through practical, done-for-you prompt packs.

## Voice
Energetic, direct, non-technical. Like a knowledgeable friend who uses AI every day.
Avoid: jargon, corporate tone, overpromising.

## Content Style
- Hook-first: grab attention in the first 2 seconds
- Practical: every tip is immediately actionable
- Real: use relatable scenarios (saving time, making money, looking professional)
- Short: TikTok/Reels format — 30-60 seconds, punchy

## Products
PDF prompt packs, $6-$14, instant download. No physical inventory, no fulfillment.
Topics: email writing, content creation, freelancer pricing, client communication, AI workflows.

## Revenue Model
Views/CPM from organic short-form video + TikTok Shop affiliate commissions + digital product sales.

## Platforms
TikTok (manual upload by owner), Instagram Reels (auto), Facebook Reels (auto), YouTube Shorts (auto).
```

- [ ] **Step 3: Create vault/TOOLS.md**

```markdown
# Available Tools — Agent Runtime

## image_generation
Generates images via OpenAI gpt-image-1.
Use for: video thumbnails, product cover images, social post visuals.
Key params: prompt (str), filename (str), size ("1024x1024" | "1024x1792" | "1792x1024")

## audio_generation
Generates speech via OpenAI TTS.
Voices: nova (energetic female), onyx (deep male), alloy, echo, fable, shimmer.
Use for: video voiceovers, audio clips.
Key params: text (str), filename (str), voice (str)

## assemble_video
Combines audio + images into a finished MP4. Call this as the final step of every video task.
Key params: audio_path (str), image_paths (list[str]), output_filename (str)

## save_video_package
Saves finished video + script to workspace/social/ready-to-post/.
Use for: completed video ready for upload/posting.
Key params: title (str), script (str), video_path (str)

## file_editor
Reads and writes files in the project workspace.
Use for: saving drafts, outputs, notes, reading task context.
Key params: operation ("read"|"write"), path (str), content (str, write only)

## create_task
Creates new task files for other agents to pick up.
Use for: Atlas spawning tasks, agents creating follow-up work.
Key params: title, body, assigned_agent, task_type, pod, priority

## web_research
Fetches and summarises content from a URL.
Use for: research, competitor analysis, trending topics.
Key params: url (str), query (str)

## etsy_listing
Creates or updates an Etsy product listing.
Use for: Market agent publishing prompt packs.
Key params: title, description, price, tags, images
```

- [ ] **Step 4: Create vault/.gitignore**

```
# track everything in the vault
```

- [ ] **Step 5: Commit vault structure**

```bash
git add vault/
git commit -m "feat: vault — AGENTS.md, SOUL.md, TOOLS.md OpenClaw workspace files"
```

---

### Task 7: Create GitHub vault repo and vault_sync.sh

**Files:**
- Create: `scripts/vault_sync.sh`

- [ ] **Step 1: Create a private GitHub repo for the vault**

Go to `https://github.com/new`:
- Repository name: `theprompt-vault` (or similar)
- Visibility: **Private**
- Do NOT initialize with README
- Click **Create repository**

Note the repo URL: `git@github.com:<YOUR_USER>/theprompt-vault.git`

- [ ] **Step 2: Initialize vault as its own git repo (do this on the VPS)**

On the VPS:

```bash
cd /home/ubuntu/vault
git init
git remote add origin git@github.com:<YOUR_USER>/theprompt-vault.git
git add -A
git commit -m "init: vault structure"
git push -u origin main
```

Expected: vault pushed to GitHub. Verify at `https://github.com/<YOUR_USER>/theprompt-vault`.

- [ ] **Step 3: Create scripts/vault_sync.sh**

```bash
#!/usr/bin/env bash
# Syncs the vault to GitHub after each execution batch.
# Runs on Linux VPS only — silently skipped if not present.
set -euo pipefail

VAULT_DIR="/home/ubuntu/vault"
cd "$VAULT_DIR"

git add -A

# Exit cleanly if nothing to commit
if git diff --cached --quiet; then
    exit 0
fi

git commit -m "vault sync: $(date -u '+%Y-%m-%d %H:%M UTC')"
git push origin main
```

- [ ] **Step 4: Copy vault_sync.sh to VPS and make executable**

On your Windows machine:

```bash
git add scripts/vault_sync.sh
git commit -m "feat: vault_sync.sh — git-push vault to GitHub after each cycle"
```

On the VPS:

```bash
cd /home/ubuntu/ai-ops
git pull origin master
chmod +x scripts/vault_sync.sh
```

- [ ] **Step 5: Test vault_sync.sh manually on VPS**

```bash
# Create a test file to give git something to commit
echo "test" > /home/ubuntu/vault/sessions/.gitkeep
bash /home/ubuntu/ai-ops/scripts/vault_sync.sh
```

Expected: `vault sync: YYYY-MM-DD HH:MM UTC` committed and pushed to GitHub.

---

### Task 8: Configure Obsidian on your Windows laptop

This task has no code.

- [ ] **Step 1: Install Obsidian**

Download and install from `https://obsidian.md` (free).

- [ ] **Step 2: Clone the vault repo locally**

In Git Bash on Windows:

```bash
cd ~/Documents
git clone git@github.com:<YOUR_USER>/theprompt-vault.git obsidian-vault
```

- [ ] **Step 3: Open vault in Obsidian**

Launch Obsidian → **Open folder as vault** → navigate to `Documents/obsidian-vault` → click **Open**.

Expected: Obsidian shows the vault with `AGENTS.md`, `SOUL.md`, `TOOLS.md`, and `sessions/` folder.

- [ ] **Step 4: Pull vault updates on demand**

Whenever you want to see what agents wrote, run in Git Bash:

```bash
cd ~/Documents/obsidian-vault && git pull origin main
```

Obsidian reloads automatically.

---

## Phase 3 — Improvement Loop

### Task 9: Create improvement_loop.py

**Files:**
- Create: `scripts/improvement_loop.py`
- Create: `tests/runner/test_improvement_loop.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runner/test_improvement_loop.py
import pytest


def test_parse_updates_extracts_changed_agent():
    from scripts.improvement_loop import _parse_updates

    response = """
AGENT: social_media_worker
CHANGED
# Spark — Updated
New improved content here.
END_AGENT

AGENT: content_worker
NO_CHANGE
END_AGENT

Summary: Updated Spark because scripts were too long.
"""
    updates, summary = _parse_updates(response)
    assert "social_media_worker" in updates
    assert "# Spark — Updated" in updates["social_media_worker"]
    assert "content_worker" not in updates
    assert "Updated Spark" in summary


def test_parse_updates_returns_empty_on_no_changes():
    from scripts.improvement_loop import _parse_updates

    response = """
AGENT: manager
NO_CHANGE
END_AGENT
"""
    updates, summary = _parse_updates(response)
    assert updates == {}


def test_parse_updates_handles_malformed_gracefully():
    from scripts.improvement_loop import _parse_updates

    updates, summary = _parse_updates("some random text with no agent blocks")
    assert updates == {}
```

- [ ] **Step 2: Run tests — expect ImportError**

```
python -m pytest tests/runner/test_improvement_loop.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create scripts/improvement_loop.py**

```python
#!/usr/bin/env python3
"""
Nightly improvement loop.
Reads today's vault sessions, calls Claude API, rewrites agent/*.md files that
underperformed, and commits the changes.

Run manually: python scripts/improvement_loop.py
Runs automatically: systemd improvement-loop.timer at 2 AM daily
"""
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
VAULT_DIR = ROOT / "vault"
AGENTS_DIR = ROOT / "agents"

_AGENTS_TO_REVIEW = [
    "manager",
    "social_media_worker",
    "digital_product_worker",
    "content_worker",
    "marketing_worker",
]

_IMPROVEMENT_SYSTEM = """\
You are the improvement engine for ThePromptVaultUS AI Operations Command Center.
Your job: analyze today's agent session data and improve agent prompt files that underperformed.

Rules:
- Only rewrite agents that produced poor output or hit errors today.
- Preserve each agent's core role — only tune the instructions and style.
- If an agent performed well, output NO_CHANGE.
- Be specific: if Spark wrote weak hooks, improve the hook-writing instructions.
- Output valid markdown that fully replaces the existing agent file.

Output format — use this exact structure for EVERY agent you review:

AGENT: <agent_name>
CHANGED
<full new markdown content for agents/<agent_name>.md>
END_AGENT

or if no change needed:

AGENT: <agent_name>
NO_CHANGE
END_AGENT

After all agent blocks, write a one-paragraph plain-text summary of what you changed and why.
"""


def _read_vault_today() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    session_dir = VAULT_DIR / "sessions" / today
    if not session_dir.exists():
        return ""
    parts = [f.read_text(encoding="utf-8") for f in sorted(session_dir.glob("*.md"))]
    return "\n\n---\n\n".join(parts)


def _read_workspace_context() -> str:
    parts = []
    for name in ("AGENTS.md", "SOUL.md", "TOOLS.md"):
        f = VAULT_DIR / name
        if f.exists():
            parts.append(f"## {name}\n{f.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def _parse_updates(response_text: str) -> tuple[dict[str, str], str]:
    """Parse Claude's response into {agent_name: new_content} and a summary string."""
    updates: dict[str, str] = {}
    summary = ""

    blocks = response_text.split("AGENT: ")
    for block in blocks[1:]:
        lines = block.strip().split("\n")
        agent_name = lines[0].strip()
        rest = "\n".join(lines[1:])
        end_idx = rest.find("END_AGENT")
        if end_idx == -1:
            continue
        body = rest[:end_idx].strip()
        if body.startswith("NO_CHANGE"):
            continue
        # Strip the "CHANGED" sentinel line if present
        body_lines = body.split("\n")
        if body_lines and body_lines[0].strip() == "CHANGED":
            body = "\n".join(body_lines[1:]).strip()
        if body:
            updates[agent_name] = body

    # Everything after the last END_AGENT is the summary
    last_end = response_text.rfind("END_AGENT")
    if last_end != -1:
        summary = response_text[last_end + len("END_AGENT"):].strip()

    return updates, summary


def _commit_improvements(agents_updated: list[str]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    msg = f"improvement-loop: {today} — {len(agents_updated)} agent(s) updated: {', '.join(agents_updated)}"
    subprocess.run(["git", "add", "agents/"], cwd=ROOT, check=False, capture_output=True)
    result = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=False, capture_output=True, text=True)
    if result.returncode == 0:
        log.info("Committed: %s", msg)
    else:
        log.warning("Git commit output: %s", result.stdout + result.stderr)


def _write_improvement_summary(summary: str, agents_updated: list[str]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    out = VAULT_DIR / "learnings" / f"{today}-overnight.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"# Improvement Loop — {today}\n"
        f"Agents updated: {', '.join(agents_updated) if agents_updated else 'none'}\n\n"
        f"{summary}\n"
    )
    out.write_text(content, encoding="utf-8")
    log.info("Summary written to %s", out)


def run() -> None:
    log.info("Improvement loop starting")

    vault_today = _read_vault_today()
    if not vault_today:
        log.info("No session data for today — skipping")
        return

    workspace_ctx = _read_workspace_context()
    agent_contents = {
        name: (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        for name in _AGENTS_TO_REVIEW
        if (AGENTS_DIR / f"{name}.md").exists()
    }

    user_prompt = (
        f"## Today's Session Data\n{vault_today}\n\n"
        f"## Workspace Context\n{workspace_ctx}\n\n"
        f"## Current Agent Files\n"
        + "\n".join(f"### {n}\n{c}" for n, c in agent_contents.items())
    )

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8192,
        system=_IMPROVEMENT_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    output = response.content[0].text
    log.info("Improvement response received (%d chars)", len(output))

    updates, summary = _parse_updates(output)
    agents_updated = []

    for agent_name, new_content in updates.items():
        if agent_name not in agent_contents:
            log.warning("Skipping unknown agent: %s", agent_name)
            continue
        (AGENTS_DIR / f"{agent_name}.md").write_text(new_content, encoding="utf-8")
        log.info("Updated agents/%s.md", agent_name)
        agents_updated.append(agent_name)

    if agents_updated:
        _commit_improvements(agents_updated)

    _write_improvement_summary(summary, agents_updated)
    log.info("Improvement loop complete — updated: %s", agents_updated or "none")


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests — expect PASS**

```
python -m pytest tests/runner/test_improvement_loop.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/improvement_loop.py tests/runner/test_improvement_loop.py
git commit -m "feat: improvement_loop — nightly agent prompt rewriter via Claude API"
```

---

### Task 10: Deploy improvement loop to VPS and dry-run

- [ ] **Step 1: Pull latest on VPS**

```bash
cd /home/ubuntu/ai-ops && git pull origin master
```

- [ ] **Step 2: Dry-run the improvement loop against real vault data**

On the VPS, after the execution loop has run at least one cycle and written vault sessions:

```bash
cd /home/ubuntu/ai-ops
source venv/bin/activate
python scripts/improvement_loop.py
```

Expected: either `No session data for today — skipping` (if no tasks ran yet) or agent files updated and a commit made.

- [ ] **Step 3: Check improvement loop timer is running**

```bash
sudo systemctl list-timers improvement-loop.timer
```

Expected: shows `NEXT` time of 02:00:00 tomorrow.

- [ ] **Step 4: Verify learnings vault entry is written**

```bash
ls /home/ubuntu/vault/learnings/
```

Expected: `YYYY-MM-DD-overnight.md` file present.

---

## Phase 4 — Dashboard Enhancement + Public Access

### Task 11: Add new API endpoints to dashboard/server.py

**Files:**
- Modify: `dashboard/server.py`

- [ ] **Step 1: Add three new endpoints to dashboard/server.py**

After the existing `/ws` endpoint (after line 68), add:

```python
import subprocess
import sys
from datetime import datetime

VAULT_DIR = Path(__file__).parent.parent / "vault"
TASKS_DIR = Path(__file__).parent.parent / "workspace" / "tasks"

_POD_MAP = {
    "spark":         ("social_media_worker", "video_production",  "social_media_pod"),
    "maker":         ("digital_product_worker", "guide_creation", "digital_products_pod"),
    "atlas":         ("manager",             "planning",          "management"),
    "trend_scan":    ("debug_worker",        "research",          "general"),
    "full_pipeline": ("manager",             "planning",          "management"),
}


@app.get("/api/status")
async def api_status():
    exec_active = False
    improve_next = "unavailable"

    if sys.platform != "win32":
        try:
            r = subprocess.run(
                ["systemctl", "is-active", "execution-loop"],
                capture_output=True, text=True, timeout=5,
            )
            exec_active = r.stdout.strip() == "active"
        except Exception:
            pass

        try:
            r2 = subprocess.run(
                ["systemctl", "show", "improvement-loop.timer",
                 "--property=NextElapseUSecRealtime", "--value"],
                capture_output=True, text=True, timeout=5,
            )
            raw = r2.stdout.strip()
            if raw and raw != "0":
                # Convert microseconds since epoch to human-readable
                ts = int(raw) // 1_000_000
                improve_next = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass

    return {"execution_loop_active": exec_active, "improvement_next_run": improve_next}


@app.post("/api/trigger")
async def api_trigger(request: Request):
    body = await request.json()
    pod = body.get("pod", "")

    if pod not in _POD_MAP:
        return {"error": f"Unknown pod '{pod}'. Valid: {list(_POD_MAP)}"}

    role, task_type, pod_name = _POD_MAP[pod]
    from runner.tools.task_creator import create_task

    result = create_task(
        title=f"Manual trigger: {pod}",
        body=(
            f"Manually triggered from dashboard at {datetime.now().isoformat()}. "
            f"Run the standard {pod} workflow for ThePromptVaultUS."
        ),
        assigned_agent=role,
        task_type=task_type,
        pod=pod_name,
        priority="high",
    )
    return result


@app.get("/api/vault/feed")
async def api_vault_feed():
    today = datetime.now().strftime("%Y-%m-%d")
    session_dir = VAULT_DIR / "sessions" / today
    if not session_dir.exists():
        return {"sessions": [], "date": today}

    sessions = []
    for f in sorted(session_dir.glob("*.md"), reverse=True)[:20]:
        first_line = f.read_text(encoding="utf-8").split("\n")[0].lstrip("# ").strip()
        sessions.append({"task_id": f.stem, "summary": first_line})

    return {"sessions": sessions, "date": today}
```

Also add `Request` to the FastAPI import at the top of `dashboard/server.py`:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
```

- [ ] **Step 2: Verify new endpoints exist**

```bash
python -c "
import uvicorn, asyncio
from dashboard.server import app
routes = [r.path for r in app.routes]
assert '/api/status' in routes, routes
assert '/api/trigger' in routes, routes
assert '/api/vault/feed' in routes, routes
print('All 3 endpoints present')
"
```

Expected: `All 3 endpoints present`

- [ ] **Step 3: Commit**

```bash
git add dashboard/server.py
git commit -m "feat: dashboard API — /api/status, /api/trigger, /api/vault/feed"
```

---

### Task 12: Update dashboard/index.html with loop status, triggers, and vault feed

**Files:**
- Modify: `dashboard/index.html`

- [ ] **Step 1: Add CSS for new panels — insert before closing `</style>` tag (before line 451)**

```css
  /* ─── LOOP STATUS ────────────────────────── */
  .loop-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 3px 0;
    font-size: 10px;
  }
  .loop-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--muted);
    display: inline-block;
    margin-right: 5px;
    vertical-align: middle;
  }
  .loop-dot.active {
    background: var(--green);
    box-shadow: 0 0 6px var(--green);
    animation: dotpulse 2s infinite;
  }

  /* ─── TRIGGER BUTTONS ────────────────────── */
  #trigger-panel { margin-top: 12px; }
  #trigger-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }
  .trigger-btn {
    background: rgba(77,159,255,0.08);
    border: 1px solid rgba(77,159,255,0.25);
    color: var(--blue);
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 9px;
    letter-spacing: 1px;
    cursor: pointer;
    font-family: 'Courier New', monospace;
    transition: all 0.2s;
  }
  .trigger-btn:hover {
    background: rgba(77,159,255,0.18);
    border-color: var(--blue);
    box-shadow: 0 0 8px rgba(77,159,255,0.3);
  }
  .trigger-btn:active { transform: scale(0.97); }
  .trigger-btn.fired { color: var(--green); border-color: var(--green); }

  /* ─── VAULT FEED ─────────────────────────── */
  #vault-feed-wrap { margin-top: 10px; }
  #vault-feed { font-size: 9px; line-height: 1.8; color: var(--muted); margin-top: 6px; }
  .vault-entry {
    padding: 2px 0;
    border-bottom: 1px solid rgba(26,37,64,0.4);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .vault-entry span { color: var(--cyan); margin-right: 6px; }
```

- [ ] **Step 2: Add loop status section to left panel — insert after the System section (after the line `<div class="queue-row"><span>Cycles</span>...`, around line 488)**

```html
    <hr class="divider">
    <div class="section-title">Loops</div>
    <div class="loop-row">
      <span><span class="loop-dot" id="exec-dot"></span>Execution</span>
      <span style="font-size:9px;color:var(--muted)" id="exec-status">—</span>
    </div>
    <div class="loop-row">
      <span style="color:var(--muted)">Next improve</span>
      <span style="font-size:9px;color:var(--muted)" id="improve-next">—</span>
    </div>
```

- [ ] **Step 3: Add trigger panel to center panel — insert after `</div>` that closes `#detail-panel` (after line 499)**

```html
    <div id="trigger-panel">
      <hr class="divider">
      <div class="section-title">Pod Triggers</div>
      <div id="trigger-buttons">
        <button class="trigger-btn" onclick="triggerPod('spark')">▶ SPARK</button>
        <button class="trigger-btn" onclick="triggerPod('maker')">▶ MAKER</button>
        <button class="trigger-btn" onclick="triggerPod('atlas')">▶ ATLAS</button>
        <button class="trigger-btn" onclick="triggerPod('trend_scan')">▶ TREND SCAN</button>
        <button class="trigger-btn" onclick="triggerPod('full_pipeline')">▶ FULL PIPELINE</button>
      </div>
    </div>
```

- [ ] **Step 4: Add vault feed section to right panel — insert after `<div id="activity-log"></div>` (after line 505)**

```html
    <hr class="divider">
    <div id="vault-feed-wrap">
      <div class="section-title">Vault Feed (today)</div>
      <div id="vault-feed">loading...</div>
    </div>
```

- [ ] **Step 5: Add JavaScript for new panels — insert before `connect();` at the bottom of the script block (before line 759)**

```javascript
// ── Loop status polling ───────────────────────────────────
async function refreshLoopStatus() {
  try {
    const r = await fetch("/api/status");
    const d = await r.json();
    const dot = document.getElementById("exec-dot");
    const statusEl = document.getElementById("exec-status");
    const nextEl = document.getElementById("improve-next");
    if (d.execution_loop_active) {
      dot.classList.add("active");
      statusEl.textContent = "running";
      statusEl.style.color = "var(--green)";
    } else {
      dot.classList.remove("active");
      statusEl.textContent = "stopped";
      statusEl.style.color = "var(--red)";
    }
    nextEl.textContent = d.improvement_next_run || "—";
  } catch {}
}
setInterval(refreshLoopStatus, 15000);
refreshLoopStatus();

// ── Pod trigger ───────────────────────────────────────────
async function triggerPod(pod) {
  const btn = [...document.querySelectorAll(".trigger-btn")]
    .find(b => b.onclick?.toString().includes(`'${pod}'`));
  try {
    const r = await fetch("/api/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pod }),
    });
    const d = await r.json();
    if (d.task_id) {
      if (btn) { btn.classList.add("fired"); setTimeout(() => btn.classList.remove("fired"), 2000); }
      addLog("trigger", `queued ${pod} → ${d.task_id}`, "done");
    } else {
      addLog("trigger", `trigger failed: ${d.error || "unknown"}`, "error");
    }
  } catch (e) {
    addLog("trigger", `trigger error: ${e}`, "error");
  }
}

// ── Vault feed ────────────────────────────────────────────
async function refreshVaultFeed() {
  try {
    const r = await fetch("/api/vault/feed");
    const d = await r.json();
    const el = document.getElementById("vault-feed");
    if (!d.sessions || d.sessions.length === 0) {
      el.textContent = "No sessions today yet.";
      return;
    }
    el.innerHTML = d.sessions.map(s =>
      `<div class="vault-entry"><span>${s.task_id}</span>${s.summary}</div>`
    ).join("");
  } catch {}
}
setInterval(refreshVaultFeed, 30000);
refreshVaultFeed();
```

- [ ] **Step 6: Verify dashboard starts without errors**

```bash
python -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765` — verify:
- Loop status row appears in left panel
- Trigger buttons appear below agent grid
- Vault feed section appears in right panel

- [ ] **Step 7: Commit**

```bash
git add dashboard/server.py dashboard/index.html
git commit -m "feat: dashboard — loop status panel, pod trigger buttons, vault feed"
```

---

### Task 13: Set up Cloudflare Tunnel for public HTTPS URL

- [ ] **Step 1: Install cloudflared on VPS**

On the VPS:

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
rm cloudflared.deb
```

Expected: `cloudflared` command available.

- [ ] **Step 2: Create a quick tunnel (no Cloudflare account needed)**

On the VPS, in a new terminal:

```bash
cloudflared tunnel --url http://127.0.0.1:8765
```

Expected output includes a line like:
```
https://random-words-here.trycloudflare.com
```

That URL is your public dashboard. Open it on your phone or any browser.

- [ ] **Step 3: Make tunnel persistent with systemd**

On the VPS:

```bash
sudo cloudflared service install
```

Then edit `/etc/cloudflared/config.yml` to add:

```yaml
tunnel: <YOUR_TUNNEL_ID>
credentials-file: /root/.cloudflared/<YOUR_TUNNEL_ID>.json
ingress:
  - hostname: <YOUR_TUNNEL_URL>
    service: http://127.0.0.1:8765
  - service: http_status:404
```

Then:

```bash
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

Expected: dashboard reachable at your Cloudflare URL after VPS reboots.

---

## Verification Checklist

After completing all phases, verify the full system end-to-end:

- [ ] `sudo systemctl status execution-loop` → `active (running)`
- [ ] `sudo systemctl list-timers improvement-loop.timer` → shows next 2 AM
- [ ] VPS `/vault/sessions/YYYY-MM-DD/` has `.md` files after execution loop runs
- [ ] `git log` in `/home/ubuntu/vault/` shows `vault sync:` commits
- [ ] GitHub private repo shows vault files pushed
- [ ] Local Obsidian opens vault and shows session notes after `git pull`
- [ ] Dashboard at Cloudflare URL shows loop status, trigger buttons, vault feed
- [ ] Clicking `▶ SPARK` trigger creates a task in `workspace/tasks/todo/`
- [ ] After 2 AM, `/vault/learnings/YYYY-MM-DD-overnight.md` exists
- [ ] `git log agents/` shows `improvement-loop:` commits after first nightly run
