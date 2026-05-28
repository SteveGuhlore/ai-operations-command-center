# Go Live — Implementation Plan 5 of 5

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ecosystem actually run and generate revenue — single-agent test harness, revenue pod task seeds for Etsy and Digital Products, Etsy API draft listing tool, a `.env` secrets file, and a continuous-run startup script.

**Architecture:** Four independent additions wired onto the existing runner infrastructure: (1) a CLI test harness so each agent can be validated one at a time before going full-auto, (2) real task files for every revenue pod so the queue has meaningful work, (3) an Etsy API tool adapter that creates draft listings (safe to test, promoted to live by flipping Level 3 config), and (4) a startup script that checks all API keys, launches the dashboard, and starts the cron runner in one command. No changes to existing test-passing code — all additions.

**Tech Stack:** Python 3.11+, anthropic SDK, openai SDK, httpx (already installed), python-dotenv (new), existing runner infrastructure.

---

## Prerequisites — What Each Agent Needs

Before running, set these environment variables. Create a file called `.env` in the project root (it is gitignored):

```
# Required for ALL agents
ANTHROPIC_API_KEY=sk-ant-...

# Required for Frame (image gen) and Echo (audio gen)
OPENAI_API_KEY=sk-...

# Required for Etsy pod (Level 3 only — leave blank until ready)
ETSY_API_KEY=your-etsy-key
ETSY_SHOP_ID=your-shop-id
```

**Per-agent requirements:**

| Agent | Needs | Can run without |
|---|---|---|
| Atlas (manager) | ANTHROPIC_API_KEY | — |
| Forge (heavy_worker) | ANTHROPIC_API_KEY | — |
| Scout (debug_worker) | ANTHROPIC_API_KEY | — |
| Muse (content_worker) | ANTHROPIC_API_KEY | — |
| Frame (media_worker) | ANTHROPIC_API_KEY + OPENAI_API_KEY | OPENAI_API_KEY (image gen skipped) |
| Echo (audio_worker) | ANTHROPIC_API_KEY + OPENAI_API_KEY | OPENAI_API_KEY (audio gen skipped) |
| Guard (guard_worker) | ANTHROPIC_API_KEY | — |
| Ledger (budget_worker) | ANTHROPIC_API_KEY | — |
| Maker (digital_product_worker) | ANTHROPIC_API_KEY | — |
| Market (marketing_worker) | ANTHROPIC_API_KEY | — |
| Tony Stocks | No API — file bridge only | — |

---

## File Map

```
.env                                    # NEW — API keys (gitignored)
runner/
  tools/
    etsy.py                             # NEW — Etsy draft listing tool
config/
  .env.example                          # NEW — template for .env
scripts/
  test_agent.py                         # NEW — single-agent test harness
  launch.py                             # NEW — one-command full system start
workspace/
  tasks/
    todo/
      POD-ETSY-001-product-listing.md   # NEW — Etsy Store Pod seed task
      POD-ETSY-002-product-images.md    # NEW — Etsy image generation seed
      POD-DIG-001-guide-creation.md     # NEW — Digital Products Pod seed
      POD-DIG-002-listing-copy.md       # NEW — Digital Products listing seed
      POD-AFF-001-review-article.md     # NEW — Affiliate Content Pod seed
      POD-VID-001-script-and-audio.md   # NEW — Short-Form Video Pod seed
      POD-LEAD-001-prospect-research.md # NEW — Lead Gen Pod seed
tests/
  runner/
    test_tools_etsy.py                  # NEW — Etsy adapter tests
```

---

## Task 1: .env Setup + python-dotenv Integration

**Files:**
- Create: `.env` (gitignored, not committed)
- Create: `config/.env.example`
- Modify: `runner/main.py` (load .env at startup)

- [ ] **Step 1: Install python-dotenv**

```powershell
python -m pip install python-dotenv
```

Add to `requirements.txt`:
```
python-dotenv>=1.0.0
```

- [ ] **Step 2: Create `config/.env.example`**

```
# Copy this file to .env in the project root and fill in your keys.

# Required for all agents
ANTHROPIC_API_KEY=sk-ant-REPLACE_ME

# Required for Frame (image gen) and Echo (audio gen)
OPENAI_API_KEY=sk-REPLACE_ME

# Required for Etsy pod (Level 3 — leave blank until ready to publish)
ETSY_API_KEY=REPLACE_ME
ETSY_SHOP_ID=REPLACE_ME
```

- [ ] **Step 3: Create `.env` in the project root**

```
ANTHROPIC_API_KEY=your-actual-key-here
OPENAI_API_KEY=your-actual-openai-key-here
ETSY_API_KEY=
ETSY_SHOP_ID=
```

(Fill in your real keys. This file is gitignored — it will never be committed.)

- [ ] **Step 4: Add dotenv load to top of `runner/main.py`**

Add these two lines immediately after the existing imports at the top of `runner/main.py`:

```python
from dotenv import load_dotenv
load_dotenv()
```

The full import block at the top of `runner/main.py` after the change:

```python
import concurrent.futures
import logging
from dotenv import load_dotenv

load_dotenv()

from runner.agents.base import AgentBase
from runner.agents.prompts import build_system_prompt
from runner.automation.level_check import is_action_allowed
from runner.bridge.tony_bridge import scan_and_process as scan_tony_bridge
from runner.ledger.budget import is_budget_exceeded
from runner.state.writer import update_agent_state
from runner.tasks.locker import acquire_lock, release_lock
from runner.tasks.reader import read_todo_tasks
from runner.tasks.router import route_task
from runner.tasks.transitions import move_task, write_task_output
```

- [ ] **Step 5: Run the full test suite to confirm nothing broke**

```powershell
python -m pytest tests/ -q --tb=short
```

Expected: 86 passed.

- [ ] **Step 6: Commit**

```powershell
git add requirements.txt config/.env.example runner/main.py
git commit -m "feat: load .env at startup with python-dotenv"
```

(Do NOT `git add .env` — it is gitignored.)

---

## Task 2: Single-Agent Test Harness

**Files:**
- Create: `scripts/test_agent.py`

This script runs one agent against one task and prints the output to the terminal. Use it to validate each agent before going full-auto.

- [ ] **Step 1: Create `scripts/test_agent.py`**

```python
"""
Single-agent test harness. Run one agent against one task file.

Usage:
    python scripts/test_agent.py --role debug_worker --task workspace/tasks/todo/SAMPLE-001-debug-worker-environment-check.md
    python scripts/test_agent.py --role content_worker --task workspace/tasks/todo/POD-ETSY-001-product-listing.md
    python scripts/test_agent.py --role digital_product_worker --task workspace/tasks/todo/POD-DIG-001-guide-creation.md
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from runner.agents.base import AgentBase
from runner.agents.prompts import build_system_prompt
from runner.tasks.reader import parse_task_file

MODELS = {
    "manager":                "claude-opus-4-7",
    "heavy_worker":           "claude-sonnet-4-6",
    "debug_worker":           "claude-haiku-4-5",
    "content_worker":         "claude-haiku-4-5",
    "media_worker":           "claude-sonnet-4-6",
    "audio_worker":           "claude-haiku-4-5",
    "guard_worker":           "claude-haiku-4-5",
    "budget_worker":          "claude-haiku-4-5",
    "digital_product_worker": "claude-sonnet-4-6",
    "marketing_worker":       "claude-sonnet-4-6",
    "market_research_worker": "claude-haiku-4-5",
}


def main():
    parser = argparse.ArgumentParser(description="Run one agent against one task file.")
    parser.add_argument("--role", required=True, help="Agent role ID (e.g. debug_worker, content_worker)")
    parser.add_argument("--task", required=True, help="Path to task .md file")
    parser.add_argument("--dry-run", action="store_true", help="Print system prompt only, no API call")
    args = parser.parse_args()

    task_path = Path(args.task)
    if not task_path.exists():
        print(f"ERROR: Task file not found: {task_path}")
        sys.exit(1)

    task = parse_task_file(task_path)
    model = MODELS.get(args.role, "claude-haiku-4-5")
    system_prompt = build_system_prompt(args.role)

    print(f"\n{'='*60}")
    print(f"  Agent: {args.role}  |  Model: {model}")
    print(f"  Task:  {task.get('task_id', task_path.name)}")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("--- SYSTEM PROMPT ---")
        print(system_prompt[:2000])
        print("--- TASK BODY ---")
        print(task.get("body", "")[:1000])
        return

    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to .env in the project root.")
        sys.exit(1)

    print("Calling Claude API...\n")
    agent = AgentBase(args.role, model, system_prompt)
    result = agent.run(task)

    print("--- OUTPUT ---")
    print(result["output"])
    print(f"\n--- COST: ${result['cost_usd']:.4f} | in: {result['input_tokens']} | out: {result['output_tokens']} ---")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify dry-run works (no API key needed)**

```powershell
python scripts/test_agent.py --role debug_worker --task workspace/tasks/todo/SAMPLE-001-debug-worker-environment-check.md --dry-run
```

Expected: Prints system prompt and task body. No API call made.

- [ ] **Step 3: Test each agent one by one (requires ANTHROPIC_API_KEY in .env)**

Run in order. Start cheapest (haiku) before expensive (opus):

```powershell
# 1. Scout — cheapest, general debugging
python scripts/test_agent.py --role debug_worker --task workspace/tasks/todo/SAMPLE-001-debug-worker-environment-check.md

# 2. Muse — content writer
python scripts/test_agent.py --role content_worker --task workspace/tasks/todo/POD-ETSY-001-product-listing.md

# 3. Maker — digital products
python scripts/test_agent.py --role digital_product_worker --task workspace/tasks/todo/POD-DIG-001-guide-creation.md

# 4. Market — marketing
python scripts/test_agent.py --role marketing_worker --task workspace/tasks/todo/POD-DIG-002-listing-copy.md

# 5. Guard — silent logger
python scripts/test_agent.py --role guard_worker --task workspace/tasks/todo/SAMPLE-003-debug-worker-batch-report.md

# 6. Ledger — budget reporter
python scripts/test_agent.py --role budget_worker --task workspace/tasks/todo/SAMPLE-003-debug-worker-batch-report.md

# 7. Forge — heavy implementation
python scripts/test_agent.py --role heavy_worker --task workspace/tasks/todo/SAMPLE-002-heavy-worker-implementation-task.md

# 8. Atlas — only run after all others confirmed working (uses Opus — most expensive)
python scripts/test_agent.py --role manager --task workspace/tasks/todo/SAMPLE-002-heavy-worker-implementation-task.md
```

Expected: Each agent returns output and a cost line. Total test cost across all 8 agents: approximately $0.05–$0.15.

- [ ] **Step 4: Commit**

```powershell
git add scripts/test_agent.py
git commit -m "feat: add single-agent test harness script"
```

---

## Task 3: Revenue Pod Task Seeds

**Files:**
- Create: `workspace/tasks/todo/POD-ETSY-001-product-listing.md`
- Create: `workspace/tasks/todo/POD-ETSY-002-product-images.md`
- Create: `workspace/tasks/todo/POD-DIG-001-guide-creation.md`
- Create: `workspace/tasks/todo/POD-DIG-002-listing-copy.md`
- Create: `workspace/tasks/todo/POD-AFF-001-review-article.md`
- Create: `workspace/tasks/todo/POD-VID-001-script-and-audio.md`
- Create: `workspace/tasks/todo/POD-LEAD-001-prospect-research.md`

These are real tasks. Each pod gets one seed task. Once an agent completes a task, it moves to `done/`. Create more by copying the format and changing the content.

- [ ] **Step 1: Create `workspace/tasks/todo/POD-ETSY-001-product-listing.md`**

```markdown
---
task_id: POD-ETSY-001
assigned_agent: content_worker
status: todo
priority: high
pod: etsy_store_pod
task_type: content_drafting
---

# Etsy Listing Copy — Digital Productivity Planner

## Goal
Write a complete Etsy listing for a digital productivity planner PDF. The planner includes: weekly schedule template, habit tracker, goal breakdown worksheet, and daily to-do template. Price: $7.99. Target buyer: remote workers and freelancers who want to get organised.

## Deliverables

**Title** (max 140 characters, include primary keyword):
Write an SEO-optimised Etsy listing title.

**Description** (400–500 words):
- Hook sentence (lead with the buyer's pain)
- What's included (bullet list)
- Who it's for
- How they get it (instant download)
- Call to action

**Tags** (13 tags, comma-separated):
Include: productivity planner, digital planner, weekly planner, printable planner, habit tracker, goal setting, remote work, freelancer planner, instant download, PDF planner, undated planner, work from home, time management

**Materials field** (Etsy requires this):
"Digital download — PDF"
```

- [ ] **Step 2: Create `workspace/tasks/todo/POD-ETSY-002-product-images.md`**

```markdown
---
task_id: POD-ETSY-002
assigned_agent: media_worker
status: todo
priority: high
pod: etsy_store_pod
task_type: image_prompt_generation
---

# Etsy Listing Images — Digital Productivity Planner

## Goal
Generate 3 Etsy listing image prompts for the digital productivity planner (PDF, $7.99, weekly schedule + habit tracker + goal worksheet + daily to-do). Then call the image_generation tool for each prompt.

## Deliverables

Generate prompts AND call image_generation for each one:

**Image 1 — Hero/Thumbnail** (filename: etsy-planner-hero.png):
Style: flat lay on a white desk with a MacBook, coffee mug, and succulents. Mockup of the planner open to the weekly schedule page. Clean, minimal, warm lighting. Aspect 1:1. No text overlays.

**Image 2 — Pages Preview** (filename: etsy-planner-preview.png):
Style: grid of 4 page screenshots arranged neatly on a white background showing each template (weekly schedule, habit tracker, goal worksheet, daily to-do). Light drop shadow. 1:1.

**Image 3 — Lifestyle** (filename: etsy-planner-lifestyle.png):
Style: a person's hands holding a printed version of the planner at a wooden desk with a warm afternoon light. Shallow depth of field. Bokeh background. Portrait crop.

Use the image_generation tool with size 1024x1024 for each image.
```

- [ ] **Step 3: Create `workspace/tasks/todo/POD-DIG-001-guide-creation.md`**

```markdown
---
task_id: POD-DIG-001
assigned_agent: digital_product_worker
status: todo
priority: high
pod: digital_products_pod
task_type: guide_creation
---

# Digital Product — "The Freelancer's Rate-Setting Guide"

## Goal
Create the complete content for a 15–20 page PDF guide titled: **"The Freelancer's Rate-Setting Guide: Stop Undercharging and Start Earning What You're Worth"**

## Audience
Freelancers with 0–3 years of experience who are undercharging, unsure how to price, or losing clients they don't want because they're too cheap and attracting clients they don't want because they're too cheap.

## Problem Solved
They don't know how to set rates confidently, negotiate without panic, or move upmarket.

## Required Sections

1. **Why Freelancers Undercharge** (psychology, fear, imposter syndrome — 400 words)
2. **The Rate Formula** (costs + profit + taxes + time — include a worked example with real numbers — 500 words)
3. **Market Research: Finding Your Real Rates** (how to research competitors without underselling — 300 words)
4. **The Rate Reveal Script** (exact word-for-word script for telling a client your rate — 200 words)
5. **Handling "That's Too Expensive"** (3 responses that work — 300 words)
6. **Raising Rates With Existing Clients** (email template included — 300 words)
7. **Moving Upmarket** (how to attract higher-paying clients — 400 words)
8. **Action Plan** (30-day checklist — 200 words)

## Format
Full markdown content, each section clearly headed. Write every section in full — no placeholders.
```

- [ ] **Step 4: Create `workspace/tasks/todo/POD-DIG-002-listing-copy.md`**

```markdown
---
task_id: POD-DIG-002
assigned_agent: marketing_worker
status: todo
priority: high
pod: digital_products_pod
task_type: listing_strategy
---

# Etsy Listing + Marketing Copy — Freelancer Rate Guide

## Goal
Write the complete Etsy listing and social media launch copy for the "Freelancer's Rate-Setting Guide" PDF ($12.99).

## Context
The guide covers: rate formula, market research, the rate reveal script, handling objections, raising rates with existing clients, and moving upmarket. 15–20 pages. Instant digital download.

## Deliverables

**1. Etsy Listing Title** (max 140 chars):
SEO-optimised, keyword-rich.

**2. Etsy Description** (500 words):
Lead with the pain (undercharging, losing money, attracting bad clients), deliver the promise, list what's inside, explain instant download, strong CTA.

**3. 13 Etsy Tags**:
Target: freelancer pricing, freelance rates, rate setting guide, freelance income, how to price, freelance business, pricing strategy, freelancer guide, raise your rates, pricing template, freelance tips, income guide, digital download

**4. Instagram Caption + 5 Hashtags** (for launch post):
Hook, story, CTA to link in bio. Casual, direct, relatable to freelancers.

**5. Email Subject Line Options** (write 3):
For announcing to a newsletter list. A/B test these.
```

- [ ] **Step 5: Create `workspace/tasks/todo/POD-AFF-001-review-article.md`**

```markdown
---
task_id: POD-AFF-001
assigned_agent: content_worker
status: todo
priority: normal
pod: affiliate_content_pod
task_type: content_drafting
---

# Affiliate Review Article — Notion (Productivity Tool)

## Goal
Write a 1,200-word affiliate review article for Notion (notion.so). Target keyword: "best productivity app for freelancers". The article should rank on Google and convert readers to Notion sign-ups via an affiliate link.

## Audience
Freelancers and remote workers looking for a productivity and project management tool. They've heard of Notion but aren't sure if it's right for them.

## Structure

1. **Intro** (150 words): Hook with the problem (scattered tasks, missed deadlines, too many apps), introduce Notion as the solution tested over 6 months.

2. **What Is Notion** (150 words): Overview, what it does, who it's made for.

3. **Key Features for Freelancers** (300 words): Client project tracking, invoice template, content calendar, weekly planner. Specific and concrete.

4. **Pros** (bullet list, 5 points, one sentence each)

5. **Cons** (bullet list, 3 points — be honest, this builds trust)

6. **Pricing** (100 words): Free tier, Plus plan. Value for freelancers.

7. **Verdict + CTA** (150 words): Clear recommendation, affiliate link placement: `[Try Notion Free →](INSERT_AFFILIATE_LINK)`

## Tone
First-person. Honest. Specific. Like a recommendation from a friend who actually uses it, not a press release.

## Output
Full article in markdown, ready to paste into a blog or Notion page.
```

- [ ] **Step 6: Create `workspace/tasks/todo/POD-VID-001-script-and-audio.md`**

```markdown
---
task_id: POD-VID-001
assigned_agent: audio_worker
status: todo
priority: normal
pod: short_form_video_pod
task_type: audio_generation
---

# Short-Form Video — 60s Script + Audio: "Stop Undercharging"

## Goal
Write a 60-second TikTok/Reels script for a video about freelancers undercharging, then generate the voiceover audio using the audio_generation tool.

## Target Audience
Freelancers who are tired of low-paying clients.

## Script Requirements
- Hook in first 3 seconds (pattern interrupt — makes them stop scrolling)
- Pain + relatable moment (seconds 3–20)
- The insight/shift (seconds 20–45)
- CTA (seconds 45–60): "Link in bio to get the rate-setting guide"
- Approximately 130 words total
- Voice: energetic but grounded — not salesy

## Deliverables

**1. Script** (write the full 60-second script):
Mark emphasis with ALL CAPS for key words.
Add [pause] where a natural beat should be.

**2. Audio file** (call audio_generation tool):
- text: [the full script]
- filename: short-form-stop-undercharging.mp3
- voice: nova

Output the script first, then call audio_generation.
```

- [ ] **Step 7: Create `workspace/tasks/todo/POD-LEAD-001-prospect-research.md`**

```markdown
---
task_id: POD-LEAD-001
assigned_agent: debug_worker
status: todo
priority: normal
pod: lead_gen_pod
task_type: reporting
---

# Lead Gen Research — Top 10 Freelance Coaching Niches

## Goal
Research and produce a structured report on the 10 most profitable freelance coaching niches in 2025–2026. This will seed the lead gen pod's outreach strategy.

## Research Questions
For each niche:
1. What type of freelancer is in this niche?
2. What's their typical hourly rate / annual income range?
3. What are their biggest pain points (that coaching solves)?
4. What platforms do they hang out on?
5. What's a realistic outreach message opener?

## Output Format

### Report: Top 10 Freelance Coaching Niches 2026

For each niche, one section:

**Niche: [name]**
- Freelancer type: ...
- Income range: ...
- Pain points: ...
- Platform: ...
- Outreach opener: "..."

## Notes
Use web_research tool if needed to validate rates and platform presence. Do not invent figures — only include what can be verified or reasonably estimated from known data.
```

- [ ] **Step 8: Commit all seed tasks**

```powershell
git add workspace/tasks/todo/
git commit -m "feat: add revenue pod seed tasks for all 7 pods"
```

---

## Task 4: Etsy Draft Listing Tool Adapter

**Files:**
- Create: `runner/tools/etsy.py`
- Create: `tests/runner/test_tools_etsy.py`

Creates draft Etsy listings via the Etsy API v3. Safe to test — drafts are not visible to buyers until manually published from Etsy's seller dashboard (or until Level 3 is enabled).

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_tools_etsy.py
import pytest
from unittest.mock import patch, MagicMock
from runner.tools.etsy import create_draft_listing, TOOL_SPEC


def test_create_draft_listing_posts_to_etsy(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "test-key")
    monkeypatch.setenv("ETSY_SHOP_ID", "12345")

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "listing_id": 999,
        "title": "Test Product",
        "state": "draft",
        "url": "https://www.etsy.com/listing/999",
    }

    with patch("runner.tools.etsy.httpx.post", return_value=mock_response):
        result = create_draft_listing(
            title="Test Product",
            description="A great product.",
            price=9.99,
            tags=["tag1", "tag2"],
        )
        assert result["success"] is True
        assert result["listing_id"] == 999
        assert result["state"] == "draft"


def test_create_draft_listing_returns_error_without_api_key(monkeypatch):
    monkeypatch.delenv("ETSY_API_KEY", raising=False)
    monkeypatch.delenv("ETSY_SHOP_ID", raising=False)
    result = create_draft_listing(title="T", description="D", price=5.0, tags=[])
    assert "error" in result


def test_create_draft_listing_handles_api_error(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "test-key")
    monkeypatch.setenv("ETSY_SHOP_ID", "12345")

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"error": "Forbidden"}

    with patch("runner.tools.etsy.httpx.post", return_value=mock_response):
        result = create_draft_listing(
            title="T", description="D", price=5.0, tags=[]
        )
        assert "error" in result


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "etsy_listing"
    assert "input_schema" in TOOL_SPEC
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/runner/test_tools_etsy.py -v
```

Expected: 4 errors — module not found.

- [ ] **Step 3: Write `runner/tools/etsy.py`**

```python
# runner/tools/etsy.py
import os
import httpx

ETSY_API_BASE = "https://openapi.etsy.com/v3/application"


def create_draft_listing(
    title: str,
    description: str,
    price: float,
    tags: list[str],
    quantity: int = 999,
    taxonomy_id: int = 2078,  # Digital downloads taxonomy
    who_made: str = "i_did",
    when_made: str = "made_to_order",
    is_digital: bool = True,
) -> dict:
    api_key = os.environ.get("ETSY_API_KEY")
    shop_id = os.environ.get("ETSY_SHOP_ID")

    if not api_key or not shop_id:
        return {"error": "ETSY_API_KEY and ETSY_SHOP_ID must be set in .env"}

    payload = {
        "title": title[:140],  # Etsy title limit
        "description": description,
        "price": round(price, 2),
        "quantity": quantity,
        "tags": tags[:13],  # Etsy tag limit
        "taxonomy_id": taxonomy_id,
        "who_made": who_made,
        "when_made": when_made,
        "is_digital": is_digital,
        "state": "draft",
    }

    try:
        response = httpx.post(
            f"{ETSY_API_BASE}/shops/{shop_id}/listings",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        data = response.json()
        if response.status_code == 201:
            return {
                "success": True,
                "listing_id": data.get("listing_id"),
                "state": data.get("state"),
                "url": data.get("url", ""),
                "title": title,
            }
        return {"error": data.get("error", f"HTTP {response.status_code}"), "status_code": response.status_code}
    except Exception as exc:
        return {"error": str(exc)}


def etsy_listing(
    title: str,
    description: str,
    price: float,
    tags: list[str],
    quantity: int = 999,
) -> dict:
    return create_draft_listing(title, description, price, tags, quantity)


TOOL_SPEC = {
    "name": "etsy_listing",
    "description": "Create a draft Etsy listing. Requires ETSY_API_KEY and ETSY_SHOP_ID in environment. Listings are created as drafts — not live until Level 3 is enabled.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Listing title (max 140 chars)"},
            "description": {"type": "string", "description": "Full listing description"},
            "price": {"type": "number", "description": "Price in USD"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 13 tags",
            },
            "quantity": {"type": "integer", "default": 999, "description": "Quantity available"},
        },
        "required": ["title", "description", "price", "tags"],
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_tools_etsy.py -v --tb=short
```

Expected: 4 PASSED.

- [ ] **Step 5: Register in tool_runner**

In `runner/agents/tool_runner.py`, add to the auto-register block at the bottom:

```python
from runner.tools.etsy import etsy_listing
register_tool("etsy_listing", etsy_listing)
```

- [ ] **Step 6: Run full test suite**

```powershell
python -m pytest tests/ -q --tb=short
```

Expected: 90 passed.

- [ ] **Step 7: Commit**

```powershell
git add runner/tools/etsy.py runner/agents/tool_runner.py tests/runner/test_tools_etsy.py
git commit -m "feat: add Etsy draft listing tool adapter"
```

---

## Task 5: One-Command Launch Script

**Files:**
- Create: `scripts/launch.py`

Starts the full system: loads `.env`, checks API keys, launches the dashboard server, and starts the cron runner — all in one command.

- [ ] **Step 1: Create `scripts/launch.py`**

```python
"""
Full system launch. Starts dashboard + cron runner.

Usage:
    python scripts/launch.py                    # Runs every hour (default)
    python scripts/launch.py --interval 1800    # Runs every 30 minutes
    python scripts/launch.py --once             # Run one cycle and exit

Open http://127.0.0.1:8765 to see the live dashboard.
Press Ctrl-C to stop everything.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

REQUIRED_KEYS = ["ANTHROPIC_API_KEY"]
OPTIONAL_KEYS = ["OPENAI_API_KEY", "ETSY_API_KEY", "ETSY_SHOP_ID"]
DASHBOARD_URL = "http://127.0.0.1:8765"


def check_keys():
    missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
    if missing:
        print(f"\nERROR: Missing required environment variables: {', '.join(missing)}")
        print("Add them to .env in the project root. See config/.env.example for the template.")
        sys.exit(1)

    optional_missing = [k for k in OPTIONAL_KEYS if not os.environ.get(k)]
    if optional_missing:
        print(f"NOTE: Optional keys not set (some tools will be skipped): {', '.join(optional_missing)}")


def start_dashboard():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "dashboard.server:app",
         "--host", "127.0.0.1", "--port", "8765"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)  # Give server time to start
    print(f"Dashboard running at {DASHBOARD_URL}")
    return proc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between cycles (default: 3600)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    print("\n" + "="*50)
    print("  AI OPS COMMAND CENTER — LAUNCH")
    print("="*50 + "\n")

    check_keys()

    dashboard_proc = start_dashboard()

    from runner.main import run_cycle

    if args.once:
        print("Running one cycle...\n")
        run_cycle()
        print("\nCycle complete. Dashboard still running.")
        print(f"View at {DASHBOARD_URL}")
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            dashboard_proc.terminate()
            print("\nStopped.")
        return

    from runner.scheduler.cron_runner import CronRunner

    print(f"Starting cron runner — cycle every {args.interval}s")
    print(f"Dashboard: {DASHBOARD_URL}")
    print("Press Ctrl-C to stop.\n")

    cron = CronRunner(interval_seconds=args.interval, callback=run_cycle)
    cron.start()

    # Run first cycle immediately
    run_cycle()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nShutting down...")
        cron.stop()
        dashboard_proc.terminate()
        print("Stopped.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it prints help without error**

```powershell
python scripts/launch.py --help
```

Expected: Prints usage, `--interval`, and `--once` options.

- [ ] **Step 3: Dry-run check (ANTHROPIC_API_KEY not set — should error cleanly)**

Temporarily clear the key and confirm the error message is helpful:

```powershell
$env:ANTHROPIC_API_KEY = ""
python scripts/launch.py --once
```

Expected: Prints `ERROR: Missing required environment variables: ANTHROPIC_API_KEY` and exits.

Restore the key:
```powershell
$env:ANTHROPIC_API_KEY = "your-key"
```

- [ ] **Step 4: Commit**

```powershell
git add scripts/launch.py
git commit -m "feat: add one-command launch script with dashboard + cron runner"
```

---

## Deployment Checklist — How to Run the Full System

After completing all tasks:

### Step 1: Set API keys
Edit `.env` in the project root. Minimum required:
```
ANTHROPIC_API_KEY=sk-ant-...
```

### Step 2: Test each agent one by one
```powershell
python scripts/test_agent.py --role debug_worker --task workspace/tasks/todo/SAMPLE-001-debug-worker-environment-check.md
python scripts/test_agent.py --role content_worker --task workspace/tasks/todo/POD-ETSY-001-product-listing.md
python scripts/test_agent.py --role digital_product_worker --task workspace/tasks/todo/POD-DIG-001-guide-creation.md
python scripts/test_agent.py --role marketing_worker --task workspace/tasks/todo/POD-DIG-002-listing-copy.md
```

Each one costs ~$0.01–$0.02. Verify the output looks good before going full-auto.

### Step 3: Run one full cycle
```powershell
python scripts/launch.py --once
```

Open http://127.0.0.1:8765 — you'll see the agent grid update in real time.

### Step 4: Run continuously
```powershell
python scripts/launch.py --interval 3600
```

Leave this running. The runner picks up any task in `workspace/tasks/todo/`, processes up to 4 at a time, and writes results to `workspace/tasks/done/`.

### Step 5: Enable Level 3 (Etsy publishing) when ready
Edit `config/automation-level.yaml`:
```yaml
current_level: 3
level_3_actions:
  etsy_publish: true   # ← flip this
  social_post: false
  paid_campaign: false
```

No code change needed. The runner will now create real Etsy listings (requires `ETSY_API_KEY` and `ETSY_SHOP_ID` in `.env`).

### Adding more tasks
Copy any task file from `workspace/tasks/todo/`, change `task_id`, update the content, drop it in `workspace/tasks/todo/`. The next cycle picks it up automatically.
