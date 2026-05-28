# Autonomous Agent Ecosystem — Design Spec
Date: 2026-05-21

## Overview

A fully autonomous, continuously operating AI operations ecosystem built on top of the existing Command Center file structure. Eleven specialized agents run scheduled Claude API calls, execute real work across all revenue pods, and report into a live 2D interactive dashboard — with minimal human involvement. Two hard stops only: configurable budget caps (managed by Ledger) and no live broker trade execution for Tony Stocks.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SCHEDULER (Windows Task Scheduler)        │
│         9am health | hourly scan | 10pm report | Fri eval   │
└────────────────────────┬────────────────────────────────────┘
                         │ triggers
┌────────────────────────▼────────────────────────────────────┐
│                   AGENT RUNNER (Python)                      │
│  - reads task queue from workspace/tasks/                    │
│  - routes tasks by task_type → agent role                    │
│  - fires Claude API calls with per-agent system prompts      │
│  - manages lock files and status transitions                 │
│  - runs tool adapters (web, image, audio, file, code)        │
│  - writes results and logs back to Command Center            │
│  - Ledger enforces budget cap (auto-pause, auto-resume)      │
└──────┬──────────────────────────────────────────────────────┘
       │ reads/writes
┌──────▼──────────────────────┐    ┌──────────────────────────┐
│  COMMAND CENTER FILE STATE  │    │  EXTERNAL SERVICES       │
│  workspace/tasks/           │    │  Claude API              │
│    todo/                    │    │  DALL-E / Stable Diff    │
│    in_progress/             │    │  ElevenLabs / OpenAI TTS │
│    review/                  │    │  Web (search + fetch)    │
│    done/                    │    │  Etsy API (Level 3+)     │
│    failed/                  │    │  Social APIs (Level 3+)  │
│  workspace/locks/           │    │  TradingBotAgentProject  │
│  workspace/logs/            │    │    (file bridge only)    │
│  workspace/reports/         │    └──────────────────────────┘
│  bridge/tony-stocks/        │
└──────┬──────────────────────┘
       │ pushed via WebSocket
┌──────▼──────────────────────────────────────────────────────┐
│                  2D DASHBOARD (local web app)                │
│  FastAPI + WebSocket server  |  HTML/CSS/JS frontend        │
│  Agent grid | Task pipeline | Pod tabs | Activity log       │
└─────────────────────────────────────────────────────────────┘
```

---

## The 11 Agents

| Agent | Role ID | Model | Primary Work |
|---|---|---|---|
| Atlas | manager | claude-opus-4-7 | Orchestration, batch planning, failure requeue |
| Forge | heavy_worker | claude-sonnet-4-6 | Feature implementation, code, refactors |
| Scout | debug_worker | claude-haiku-4-5 | Validation, debugging, docs, queue scans |
| Muse | content_worker | claude-haiku-4-5 | Copy, captions, articles, content drafts |
| Frame | media_worker | claude-sonnet-4-6 + image API | Image prompts, asset generation, media packaging |
| Echo | audio_worker | claude-haiku-4-5 + TTS API | Audio scripts, voice prompts, narration |
| Guard | guard_worker | claude-haiku-4-5 | Silent policy logger — no blocking |
| Ledger | budget_worker | claude-haiku-4-5 | Cost tracking, budget cap enforcement |
| Maker | digital_product_worker | claude-sonnet-4-6 | Digital products, PDFs, guides, templates |
| Market | marketing_worker | claude-sonnet-4-6 | Listings, campaigns, hooks, positioning |
| Tony Stocks | market_research_worker | file bridge | Stock research via TradingBotAgentProject |

### Guard behavior change
Guard no longer blocks execution. It runs as a silent pass-through: reads task output, logs any policy observations to `workspace/logs/guard/`, and always returns `pass`. The log is visible on the dashboard. No action is gated.

### Ledger behavior
Ledger tracks every API call cost in `workspace/ledger/daily-spend.json`. If the configured daily cap is hit:
- Runner auto-pauses new task dispatch
- Dashboard shows a budget-paused state on all agent cards
- At midnight (or configurable reset interval), spend resets and runner auto-resumes
- Cap is set in `config/budgets.yaml` — no code change needed to adjust it

---

## Revenue Pods

Each pod is a logical grouping of agents + task types. The runner reads pod assignment from task frontmatter and routes accordingly.

| Pod | Key Agents | External Tools |
|---|---|---|
| Etsy Store Pod | Muse, Frame, Market | image_generation, Etsy API (Level 3+) |
| Dropshipping Pod | Muse, Frame, Market | image_generation, web_research |
| Affiliate Content Pod | Muse, Scout, Market | web_research, file_editor |
| Short-Form Video Pod | Frame, Muse, Echo | image_generation, audio_generation, video_generation |
| Digital Products Pod | Maker, Muse, Frame | file_editor, image_generation |
| Lead Gen Pod | Muse, Scout, Market | web_research, file_editor |
| Stock Research Pod | Tony Stocks, Scout, Ledger | file bridge, web_research |
| App SaaS Pod | Forge, Scout, Muse | code_runner, file_editor |

---

## Agent Runner — Core Components

### `runner/main.py`
Entry point. On each trigger:
1. Check Ledger budget — if capped, exit cleanly
2. Atlas reads queue depth and creates a batch plan
3. Runner dispatches tasks to agents in parallel (up to configured concurrency)
4. Each agent call returns output + cost
5. Ledger records cost
6. Runner writes results, updates task status, releases locks
7. Dashboard state file is updated

### `runner/agents/`
One file per agent role. Each contains:
- System prompt built from agent `.md` + YAML config
- Tool list the agent is allowed to call
- Model assignment
- Max retries

### `runner/tools/`
One adapter per tool:
- `web.py` — WebSearch + WebFetch via Claude tool use
- `image.py` — DALL-E 3 or Stable Diffusion (config-driven)
- `audio.py` — ElevenLabs or OpenAI TTS
- `video.py` — stub for future video gen API
- `files.py` — workspace file read/write
- `code.py` — PowerShell subprocess runner
- `cost.py` — Ledger JSON write

### `runner/scheduler/`
- `setup_windows_scheduler.py` — one-time setup script that registers all four schedules in Windows Task Scheduler
- `cron_runner.py` — alternative file-based cron watcher for dev/testing without Task Scheduler

### `runner/bridge/`
- `tony_bridge.py` — watches `bridge/tony-stocks/` for new files from TradingBotAgentProject, converts them into task files in the `todo/` queue for the Stock Research Pod

---

## Plugin Integration

Claude Code plugins wire into agent sessions as follows:

| Plugin | Used By | How |
|---|---|---|
| superpowers:dispatching-parallel-agents | Atlas | System prompt segment for batch planning |
| feature-dev | Forge | System prompt segment for implementation tasks |
| superpowers:systematic-debugging | Scout | System prompt segment for debug tasks |
| code-review | Scout + Atlas | System prompt segment for review tasks |
| superpowers:test-driven-development | Forge | System prompt segment for test repair tasks |
| schedule | Runner setup | Manages cron trigger registration |
| frontend-design | Forge | System prompt segment for UI tasks (Star Office, Dashboard) |

Skill content is read from `~/.claude/plugins/cache/claude-plugins-official/` at runner startup and injected into the relevant agent system prompts. No plugin is called at runtime — the content becomes part of the agent's instructions.

---

## 2D Dashboard

### Stack
- Backend: Python FastAPI + WebSocket server (runs alongside the runner)
- Frontend: Single HTML file + vanilla JS (no framework, instant load)
- State: `workspace/dashboard-state.json` written by runner after each cycle

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  AI OPS COMMAND CENTER  v1.0     [Automation: Level 2]  $2.14/d │
├──────────────┬──────────────────────────────────┬───────────────┤
│  TASK QUEUE  │          AGENT GRID              │ ACTIVITY LOG  │
│              │                                  │               │
│  todo    12  │  ┌──────┐ ┌──────┐ ┌──────┐     │ 09:14 Forge   │
│  active   4  │  │Atlas │ │Forge │ │Scout │     │ impl task #42 │
│  review   1  │  │ ████ │ │ ████ │ │ idle │     │               │
│  done    47  │  │review│ │coding│ │      │     │ 09:13 Muse    │
│  failed   0  │  └──────┘ └──────┘ └──────┘     │ wrote listing │
│              │                                  │               │
│  PODS        │  ┌──────┐ ┌──────┐ ┌──────┐     │ 09:12 Market  │
│  ▶ Etsy      │  │ Muse │ │Frame │ │ Echo │     │ built hook    │
│  ○ Dropship  │  │write │ │image │ │ idle │     │               │
│  ○ Affiliate │  └──────┘ └──────┘ └──────┘     │ 09:11 Guard   │
│  ○ Video     │                                  │ logged pass   │
│  ○ Digital   │  ┌──────┐ ┌──────┐ ┌──────┐     │               │
│  ○ Lead Gen  │  │Guard │ │Ledger│ │Maker │     │ 09:10 Atlas   │
│  ○ Stock     │  │ log  │ │$2.14 │ │build │     │ batch planned │
│  ○ SaaS      │  └──────┘ └──────┘ └──────┘     │               │
│              │                                  │               │
│  BUDGET      │  ┌──────┐ ┌──────┐              │               │
│  $2.14/$50   │  │Market│ │ Tony │              │               │
│  ████░░░░░░  │  │plan  │ │bridg │              │               │
│              │  └──────┘ └──────┘              │               │
└──────────────┴──────────────────────────────────┴───────────────┘
```

### Agent card states
- **idle** — gray, no glow
- **working** — green pulse glow
- **error / failed** — red glow
- **budget paused** — orange glow, all cards simultaneously
- **offline** (Tony Stocks when bridge has no data) — dim, dashed border

### Interactions
- Click agent card → side panel opens with last task title, log tail, model used, cost of last run
- Click pod name → filters task queue and log to that pod only
- Click failed task → shows error and retry button (one manual retry available)
- Budget bar → click to open `config/budgets.yaml` directly

---

## Tony Stocks Bridge

TradingBotAgentProject writes output files to a shared folder:
```
bridge/tony-stocks/
  scanner-YYYY-MM-DD.json
  watchlist-YYYY-MM-DD.json
  paper-trade-YYYY-MM-DD.json
```

`tony_bridge.py` watches this folder. On new file detection:
1. Parses the file into a task spec
2. Writes a task to `workspace/tasks/todo/` with `pod: stock_research_pod`
3. Scout picks it up, summarizes, routes to Ledger for cost check, Atlas for batch review
4. Output written to `workspace/reports/stock/`

Tony Stocks does not make API calls directly. The bridge converts file data into tasks.

---

## Automation Level

System starts at **Level 2** (draft generation, no human approval gates). Level 3 (queued execution requiring approval) actions — Etsy publishing, social posting, paid campaigns — are wired but disabled. Enabling them requires a single config change in `config/automation-level.yaml`. No code change needed to advance levels.

---

## Build Sequence

1. Agent Runner core — task pickup, lock files, status transitions, Claude API calls
2. Per-agent system prompts — built from existing `.md` + YAML files
3. Tool adapters — `files.py`, `web.py`, `code.py`, `cost.py` first
4. Ledger budget enforcement — daily cap, auto-pause, auto-resume
5. Dashboard backend — FastAPI + WebSocket + state file writer
6. Dashboard frontend — agent grid, task queue, activity log, pod tabs
7. Windows Scheduler setup — register all four cron triggers
8. Tony Stocks bridge — file watcher + task converter
9. Image/audio tool adapters — `image.py`, `audio.py`
10. Plugin skill injection — load skill content into agent system prompts
11. Level 3 action stubs — Etsy, social scheduler (disabled until config unlock)
