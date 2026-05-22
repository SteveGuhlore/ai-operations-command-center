# Agentic OS Design — ThePromptVaultUS
**Date:** 2026-05-22  
**Status:** Approved  
**Brand:** ThePromptVaultUS  

---

## Problem Statement

The current AI Operations Command Center runs agents locally on a Windows machine, has no persistent cross-session memory, and has no mechanism for self-improvement. Agents repeat the same mistakes, the system stops when the machine sleeps, and there is no structured way to observe what worked vs. what failed.

This design replaces that with a Dual Loop Agentic OS: an execution loop that runs tasks 24/7 on a cloud VPS, and an improvement loop that reads agent output nightly and rewrites agent definitions to get measurably better over time.

---

## Architecture Overview

Two fully autonomous loops share one Obsidian vault on a single Linux VPS. The vault syncs to the user's laptop for viewing in the Obsidian app.

```
┌─────────────────────────────────────────────────────┐
│                    LINUX VPS                         │
│                                                      │
│  EXECUTION LOOP (every 5 min)                        │
│  Python Runner → Claude API → Revenue Pods           │
│  Spark / Maker / Affiliate / Atlas                   │
│              ↓ writes                                │
│                   /vault/                            │
│              ↑ reads                                 │
│  IMPROVEMENT LOOP (nightly 2 AM)                     │
│  OpenClaw + Claude Code → rewrites agents/ → commit  │
│                                                      │
│  FastAPI Dashboard :8765 (Cloudflare Tunnel)         │
└─────────────────────────────────────────────────────┘
         ↕ git sync
  Laptop: Obsidian app opens synced /vault/
```

---

## Layer 1: VPS Infrastructure

**Provider:** Hetzner CX22 (~$4.15/month)  
**Spec:** 2 vCPU, 4GB RAM, 40GB SSD, Ubuntu 22.04 LTS

### Directory Layout
```
/home/ubuntu/
├── ai-ops/                  ← project repo (git clone)
│   ├── runner/
│   ├── agents/              ← improvement loop rewrites these
│   ├── workspace/
│   └── .env                 ← API keys (never in git)
└── vault/                   ← Obsidian vault (separate git repo)
```

### systemd Services
| Service | Trigger | Command |
|---|---|---|
| `execution-loop.service` | Boot + auto-restart | `python scripts/launch.py --interval 300` |
| `improvement-loop.timer` | 2 AM daily | fires `improvement-loop.service` |
| `improvement-loop.service` | Timer | OpenClaw nightly job |

### Public Dashboard Access
Cloudflare Tunnel provides a free HTTPS URL (`https://<name>.trycloudflare.com`) without port forwarding. Accessible from phone or browser anywhere.

### Cost
| Item | Monthly |
|---|---|
| Hetzner CX22 VPS | ~$4.15 |
| Claude API (existing $2/day cap) | ~$60 |
| Cloudflare Tunnel | Free |
| Domain (optional) | ~$1 |

---

## Layer 2: The Vault (Obsidian Memory)

A folder of markdown files on the VPS. Agents write to it during execution. OpenClaw reads it during improvement. The user views it via Obsidian on their laptop.

### Structure
```
/vault/
├── AGENTS.md          ← OpenClaw workspace injection: who the agents are
├── SOUL.md            ← OpenClaw workspace injection: brand voice, values, goals
├── TOOLS.md           ← OpenClaw workspace injection: available tools + when to use
│
├── sessions/
│   └── YYYY-MM-DD/
│       └── <task-id>-result.md   ← per-task: agent, output quality, tokens, errors
│
├── learnings/
│   ├── spark-video-wins.md       ← content formats and hooks that performed well
│   ├── maker-product-patterns.md ← prompt packs that converted vs. didn't
│   └── atlas-spawn-quality.md    ← which task types produce best ROI
│
├── errors/
│   ├── known-failures.md         ← recurring errors + resolutions
│   └── api-issues.md             ← rate limits, timeouts, model errors
│
└── revenue/
    ├── daily-log.md              ← spend vs. output quality per day
    └── pod-performance.md        ← which pod delivers most value
```

### Sync Strategy
- VPS pushes vault to private git repo after each execution batch
- Laptop pulls that repo — Obsidian opens it as a local folder
- User sees agent output within minutes of it being written

### OpenClaw Workspace Files
`AGENTS.md`, `SOUL.md`, and `TOOLS.md` are injected into every Claude Code session automatically by OpenClaw. They define who the agents are, what the brand stands for, and what tools exist. The improvement loop updates these files nightly as it learns.

---

## Layer 3: The Execution Loop

The existing Python runner, minimally modified. One new component: `VaultWriter`.

### Flow
```
Every 5 minutes:
1. CronRunner fires
2. Atlas checks queue → spawns tasks if < 3 pending
3. ThreadPoolExecutor runs up to 4 tasks concurrently
4. Agent executes via Claude API tool_use loop
5. Output saved to workspace/outputs/ (unchanged)
6. ★ VaultWriter saves session summary to /vault/sessions/YYYY-MM-DD/
7. Task moves to done/ or failed/
8. Git push vault repo
```

### New Code
| File | Description | Size |
|---|---|---|
| `runner/tools/vault_writer.py` | Writes per-task session summary to vault | ~60 lines |
| `runner/agents/tool_runner.py` | Register vault_writer as a tool (1 line change) | +1 line |

### Session Summary Format (written by VaultWriter)
```markdown
# <task-id> — <agent-name>
Date: YYYY-MM-DD HH:MM
Status: done / failed
Tokens: XXXX input / XXXX output
Duration: Xs
Tools used: image, audio, save_video_package
Errors: none / <description>

## Output Quality Notes
<brief summary of what was produced>
```

### What Does NOT Change
- Runner loop, CronRunner, ThreadPoolExecutor
- Agent definitions (until improvement loop rewrites them)
- Task file format (YAML frontmatter .md)
- Budget/Ledger system
- Dashboard WebSocket server

---

## Layer 4: The Improvement Loop

Entirely new. Runs nightly at 2 AM. Uses OpenClaw + Claude Code + ClawHub's `self-improving-agent` skill.

### Flow
```
2 AM daily:
1. systemd timer triggers improvement-loop.service
2. Claude Code session starts — OpenClaw injects AGENTS.md, SOUL.md, TOOLS.md
3. self-improving-agent skill activates (from ClawHub: pskoett/self-improving-agent)
4. Reads /vault/sessions/ from past 24h
5. Reads /vault/errors/ and /vault/revenue/
6. Generates improvement report:
   - 3 best-performing patterns
   - 3 worst-performing patterns
   - Specific prompt/config changes proposed
7. Rewrites agent files in agents/ where needed
8. Updates SOUL.md + AGENTS.md with new learnings
9. Git commits: "improvement-loop: YYYY-MM-DD — N agents updated"
10. Writes summary to /vault/learnings/YYYY-MM-DD-overnight.md
```

### Safeguards
- Improvement loop only rewrites `agents/` and vault files
- Never touches `runner/`, `scripts/`, `.env`, task files, or budget system
- Git commit history provides full rollback if a rewrite degrades performance
- If no session data exists for the day, loop exits cleanly without making changes

### Compounding Effect
| Timeline | State |
|---|---|
| Day 1 | Agents run as-is |
| Day 7 | Prompts tuned to 7 days of real output data |
| Day 30 | Content formats, hooks, and product copy optimised specifically for ThePromptVaultUS |
| Day 90 | System has converged on what works — minimal human intervention needed |

---

## Layer 5: Dashboard Enhancement

Existing FastAPI dashboard at port 8765, enhanced with loop controls and vault visibility.

### New UI Panels

**Loop Status**
- Execution loop: live status, active task count, today's spend
- Improvement loop: countdown to next run, last run date, agents updated count

**One-Click Pod Triggers**
Buttons that inject a high-priority task directly into `workspace/tasks/todo/` without touching the terminal:
- `[▶ Run Spark]` `[▶ Run Maker]` `[▶ Run Atlas]`
- `[▶ Morning Trend Scan]` `[▶ Full Pipeline]`

**Vault Activity Feed**
- Last 24h session summaries pulled from `/vault/sessions/`
- Improvement log: what the nightly loop changed and why

### What Does NOT Change
- Existing WebSocket live feed
- Task list viewer
- Agent output viewer

---

## Implementation Phases

### Phase 1 — VPS + Execution Loop (Week 1)
1. Provision Hetzner VPS
2. Clone project, configure `.env`, install Python deps
3. Build `vault_writer.py` and wire into tool runner
4. Create vault repo and directory structure
5. Set up `execution-loop.service` with systemd
6. Verify execution loop runs end-to-end on VPS

### Phase 2 — Memory Layer (Week 1-2)
1. Create `AGENTS.md`, `SOUL.md`, `TOOLS.md` in vault
2. Set up vault git repo + sync script
3. Configure Obsidian on laptop to open synced vault folder
4. Verify agents are writing session summaries correctly

### Phase 3 — Improvement Loop (Week 2)
1. Install Claude Code + OpenClaw on VPS
2. Install `self-improving-agent` from ClawHub
3. Write improvement loop entry script
4. Set up `improvement-loop.timer` + service
5. Dry-run improvement loop on existing vault data

### Phase 4 — Dashboard + Public Access (Week 2-3)
1. Add loop status panel to FastAPI dashboard
2. Add one-click pod trigger buttons
3. Add vault activity feed
4. Set up Cloudflare Tunnel for HTTPS public URL

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Vault git host | GitHub private repo | Free, easiest setup, already using git |
| Improvement loop safety gate | None — auto-commit | Full autonomy, git history is the rollback |
| Dashboard authentication | None — open URL | Simplicity; no sensitive data exposed via dashboard |
