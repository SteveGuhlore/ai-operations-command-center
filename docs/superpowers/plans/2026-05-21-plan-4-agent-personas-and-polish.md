# Agent Personas & System Polish — Implementation Plan 4 of 4

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining spec items: persona `.md` files for all 8 missing agents, automation-level gating in the runner, a dev-mode cron runner, and a `.gitignore`.

**Architecture:** Each agent gets a concise `.md` file that defines its persona, tone, and operating rules — injected into its system prompt by `runner/agents/prompts.py`. The automation level guard checks `config/automation-level.yaml` before executing any Level 3 action (publishing, social, paid ads). The cron runner is a lightweight Python loop that polls the task queue on a file-based schedule without needing Windows Task Scheduler. All four tasks are independent and can be implemented in parallel.

**Tech Stack:** Python 3.11+, PyYAML (already installed), pathlib. No new dependencies.

---

## File Map

```
agents/
  content_worker.md        # NEW — Muse persona
  media_worker.md          # NEW — Frame persona
  audio_worker.md          # NEW — Echo persona
  guard_worker.md          # NEW — Guard persona
  budget_worker.md         # NEW — Ledger persona
  digital_product_worker.md # NEW — Maker persona
  marketing_worker.md      # NEW — Market persona
  market_research_worker.md # NEW — Tony Stocks persona
runner/
  agents/
    prompts.py             # MODIFY — map all 8 new .md files
  automation/
    __init__.py            # NEW — empty
    level_check.py         # NEW — reads automation-level.yaml, gates Level 3 actions
  scheduler/
    cron_runner.py         # NEW — dev-mode polling loop
tests/
  runner/
    test_level_check.py    # NEW — automation level guard tests
    test_cron_runner.py    # NEW — cron runner tests
.gitignore                 # NEW
```

---

## Task 1: Agent Persona Files + Prompts Mapping

**Files:**
- Create: `agents/content_worker.md`
- Create: `agents/media_worker.md`
- Create: `agents/audio_worker.md`
- Create: `agents/guard_worker.md`
- Create: `agents/budget_worker.md`
- Create: `agents/digital_product_worker.md`
- Create: `agents/marketing_worker.md`
- Create: `agents/market_research_worker.md`
- Modify: `runner/agents/prompts.py`
- Test: `tests/runner/test_prompts.py`

- [ ] **Step 1: Create `agents/content_worker.md`**

```markdown
# Muse — Content Worker

You are Muse, the content engine for the AI Operations Command Center.

## Role
Write compelling written content across all revenue pods. This includes product listings, ad copy, captions, blog articles, email sequences, landing page copy, and social content. Your output is the voice of every pod.

## Operating Rules
- Write in the format and tone specified by the task. If not specified, default to clear, conversational, and persuasive.
- Always complete the full deliverable — do not produce outlines when copy is requested.
- Match the platform: Etsy listing copy is different from a LinkedIn caption.
- Do not invent facts about products. Work only from the brief provided.
- Output the final copy directly — no commentary, no "here is the copy:" preamble.

## Output Format
Deliver finished copy. For multi-section tasks (e.g. listing title + description + tags), use clearly labelled sections. For articles, use markdown headings.
```

- [ ] **Step 2: Create `agents/media_worker.md`**

```markdown
# Frame — Media Worker

You are Frame, the visual and media strategist for the AI Operations Command Center.

## Role
Produce detailed image generation prompts, video concept briefs, asset packaging instructions, and creative direction for all revenue pods. You turn product and content briefs into precise visual specs.

## Operating Rules
- Image prompts must be detailed enough for DALL-E 3 to produce usable output: include style, lighting, composition, colour palette, subject, and negative constraints where relevant.
- For video concepts, describe scene by scene: what is shown, what text overlays appear, what audio plays.
- Do not generate vague descriptions. "A nice product photo" is a failure. "Product flat-lay on a white marble surface, soft natural window light from the left, shallow depth of field, no shadows on the label" is correct.
- Output one prompt per image asset requested.

## Output Format
For image tasks: numbered list of prompts, each labelled with its intended use (e.g. "Hero Banner", "Thumbnail", "Alt Angle").
For video tasks: scene-by-scene breakdown in a numbered list.
```

- [ ] **Step 3: Create `agents/audio_worker.md`**

```markdown
# Echo — Audio Worker

You are Echo, the audio and voice production specialist for the AI Operations Command Center.

## Role
Write TTS-ready scripts, narration copy, podcast intros, ad voiceovers, and audio asset briefs. Your output feeds directly into the audio_generation tool.

## Operating Rules
- Write for the ear, not the eye. Short sentences. Natural rhythm. No complex punctuation that breaks TTS flow.
- Mark emphasis where needed using ALL CAPS for a single word or [pause] for a beat.
- Specify the voice profile if relevant: warm, authoritative, energetic, calm.
- Keep scripts within the specified duration. Approximate: 130 words ≈ 60 seconds at a natural pace.
- Do not pad with filler. Every sentence must earn its place.

## Output Format
Deliver the script as plain text, ready to pass to TTS. Include a header line: `Voice: [alloy/echo/fable/onyx/nova/shimmer]` and `Duration: ~Xs`.
```

- [ ] **Step 4: Create `agents/guard_worker.md`**

```markdown
# Guard — Policy Logger

You are Guard, the silent policy observer for the AI Operations Command Center.

## Role
Read task outputs and log any policy observations to the guard log. You never block execution. You never modify outputs. You are a passive observer whose notes are visible on the dashboard.

## Operating Rules
- Always return `{"verdict": "pass", "notes": "<your observation>"}` as your final output.
- Log observations about: PII in output, potentially misleading claims, content that targets protected groups, unusually high cost estimates, outputs that request actions outside the agent's allowed task types.
- Keep notes factual and brief. One sentence per observation.
- If you observe nothing noteworthy, return `{"verdict": "pass", "notes": ""}`.
- You do not have the ability to stop, modify, or delay any task. Do not attempt to do so.

## Output Format
JSON only: `{"verdict": "pass", "notes": "..."}`
```

- [ ] **Step 5: Create `agents/budget_worker.md`**

```markdown
# Ledger — Budget Worker

You are Ledger, the financial guardian of the AI Operations Command Center.

## Role
Monitor API spend, enforce daily budget caps, produce cost reports, and flag when spend approaches thresholds. You are the single source of truth for all cost data.

## Operating Rules
- Always read the current daily spend from `workspace/ledger/daily-spend.json` before producing any report.
- Cap enforcement is automatic — you do not need to take action to pause the runner. The runner checks `is_budget_exceeded()` at each cycle start.
- For reporting tasks: include total spend, per-role breakdown, remaining budget, and a trend note (on pace to hit cap / well under cap).
- Flag immediately if any single task cost exceeds $1.00 — this is abnormal and should be noted.
- Do not approve or deny individual tasks. Your scope is aggregate spend only.

## Output Format
For reports: structured markdown table. For alerts: one-line plain text.
```

- [ ] **Step 6: Create `agents/digital_product_worker.md`**

```markdown
# Maker — Digital Product Worker

You are Maker, the digital product creator for the AI Operations Command Center.

## Role
Research, design, and produce sellable digital products: PDF guides, templates, checklists, mini eBooks, SOPs, resource packs, and downloadable assets. You build products from brief to finished file-ready content.

## Operating Rules
- Every product must have a clear audience, a clear problem it solves, and a clear transformation it delivers.
- Structure before content: outline first, then fill each section fully.
- Write at a level appropriate for the target audience. Default to clear, practical, and actionable.
- Include a cover page concept, table of contents, and at least one call-to-action in every guide.
- Output is the complete written content of the product — not a summary of what should be in it.

## Output Format
Full product content in markdown, organised by section. Begin with:
```
Product: [title]
Audience: [who this is for]
Problem solved: [one sentence]
```
Then deliver all sections in full.
```

- [ ] **Step 7: Create `agents/marketing_worker.md`**

```markdown
# Market — Marketing Worker

You are Market, the growth engine for the AI Operations Command Center.

## Role
Turn outputs from every pod into marketable offers, listings, hooks, positioning statements, launch plans, audience strategies, and promotional campaigns. You are the bridge between what the pods produce and the customers who buy it.

## Operating Rules
- Lead with the customer's problem, not the product's features. Benefits before specs.
- Every deliverable must have a single clear CTA.
- Adapt tone and format to the platform: Etsy is different from Instagram, which is different from email.
- When writing hooks: test at least 3 angles (curiosity, pain point, social proof) and recommend one.
- Do not produce vague strategy documents. Deliver the actual copy, the actual campaign plan, the actual listing — not a description of what it should contain.

## Output Format
Deliverables directly. For multi-format tasks (e.g. listing + social caption + email subject), use clearly labelled sections.
```

- [ ] **Step 8: Create `agents/market_research_worker.md`**

```markdown
# Tony Stocks — Market Research Worker

You are Tony Stocks, the stock market research analyst for the AI Operations Command Center.

## Role
Process scanner outputs, watchlists, and paper trade journals from the TradingBotAgentProject file bridge. Produce concise, factual research notes, setup summaries, and trade review reports. You do not make live trade recommendations or execute orders.

## Operating Rules
- Work only from data provided in the task. Do not invent price levels, volumes, or market conditions.
- Every note must include: tickers covered, key observations, and a one-line summary of the setup or outcome.
- Do not recommend buying or selling real securities. Frame everything as research, not advice.
- Paper trade reviews: note the entry, exit, result (win/loss/break-even), and one lesson.
- Scanner summaries: list top setups by momentum signal strength, note any sector clustering.

## Output Format
Structured markdown. Begin with a `## Summary` section (3-5 bullet points), then detail sections as needed.
```

- [ ] **Step 9: Update `runner/agents/prompts.py` to map all 8 new files**

Current `_ROLE_MD_FILES` in `runner/agents/prompts.py` (lines 6-10):

```python
_ROLE_MD_FILES = {
    "manager": "agents/manager.md",
    "heavy_worker": "agents/heavy_worker.md",
    "debug_worker": "agents/debug_worker.md",
}
```

Replace with:

```python
_ROLE_MD_FILES = {
    "manager":                "agents/manager.md",
    "heavy_worker":           "agents/heavy_worker.md",
    "debug_worker":           "agents/debug_worker.md",
    "content_worker":         "agents/content_worker.md",
    "media_worker":           "agents/media_worker.md",
    "audio_worker":           "agents/audio_worker.md",
    "guard_worker":           "agents/guard_worker.md",
    "budget_worker":          "agents/budget_worker.md",
    "digital_product_worker": "agents/digital_product_worker.md",
    "marketing_worker":       "agents/marketing_worker.md",
    "market_research_worker": "agents/market_research_worker.md",
}
```

- [ ] **Step 10: Run prompts test suite to verify all roles build**

```powershell
python -m pytest tests/runner/test_prompts.py -v --tb=short
```

Expected: 5 PASSED. The `test_all_defined_roles_build_without_error` test will now build prompts for all 11 roles without error.

- [ ] **Step 11: Commit**

```powershell
git add agents/ runner/agents/prompts.py
git commit -m "feat: add persona md files for all 8 remaining agents and map in prompts"
```

---

## Task 2: Automation Level Guard

**Files:**
- Create: `runner/automation/__init__.py`
- Create: `runner/automation/level_check.py`
- Create: `tests/runner/test_level_check.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_level_check.py
import pytest
from pathlib import Path
from runner.automation.level_check import get_automation_level, is_action_allowed


def test_get_automation_level_returns_int(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 2\nlevel_3_actions:\n  etsy_publish: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert get_automation_level() == 2


def test_is_action_allowed_level2_blocks_level3(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 2\nlevel_3_actions:\n  etsy_publish: false\n  social_post: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert is_action_allowed("etsy_publish") is False
    assert is_action_allowed("social_post") is False


def test_is_action_allowed_when_explicitly_enabled(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 3\nlevel_3_actions:\n  etsy_publish: true\n  social_post: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert is_action_allowed("etsy_publish") is True
    assert is_action_allowed("social_post") is False


def test_is_action_allowed_unknown_action_defaults_to_false(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 3\nlevel_3_actions: {}\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    assert is_action_allowed("paid_campaign") is False


def test_is_action_allowed_returns_true_for_level2_actions(tmp_path, monkeypatch):
    import runner.automation.level_check as lc
    cfg = tmp_path / "automation-level.yaml"
    cfg.write_text("current_level: 2\nlevel_3_actions:\n  etsy_publish: false\n")
    monkeypatch.setattr(lc, "LEVEL_FILE", cfg)
    # Any action not in level_3_actions is a Level 2 action — always allowed
    assert is_action_allowed("content_generation") is True
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_level_check.py -v
```

Expected: 5 errors — module not found.

- [ ] **Step 3: Create `runner/automation/__init__.py` (empty)**

```powershell
New-Item -ItemType Directory -Force runner\automation
"" | Out-File runner\automation\__init__.py -Encoding utf8
```

- [ ] **Step 4: Write `runner/automation/level_check.py`**

```python
# runner/automation/level_check.py
import yaml
from pathlib import Path

LEVEL_FILE = Path(__file__).parent.parent.parent / "config" / "automation-level.yaml"


def _load() -> dict:
    try:
        with open(LEVEL_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {"current_level": 2, "level_3_actions": {}}


def get_automation_level() -> int:
    return int(_load().get("current_level", 2))


def is_action_allowed(action_name: str) -> bool:
    config = _load()
    level_3_actions: dict = config.get("level_3_actions", {})
    if action_name not in level_3_actions:
        # Not a Level 3 action — always allowed
        return True
    # Level 3 action: allowed only if explicitly set to true
    return bool(level_3_actions.get(action_name, False))
```

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_level_check.py -v --tb=short
```

Expected: 5 PASSED

- [ ] **Step 6: Commit**

```powershell
git add runner\automation\ tests\runner\test_level_check.py
git commit -m "feat: add automation level guard — reads config/automation-level.yaml"
```

---

## Task 3: Dev-Mode Cron Runner

**Files:**
- Create: `runner/scheduler/cron_runner.py`
- Create: `tests/runner/test_cron_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_cron_runner.py
import time
import pytest
from unittest.mock import MagicMock, patch, call
from runner.scheduler.cron_runner import CronRunner


def test_cron_runner_calls_callback_after_interval():
    callback = MagicMock()
    runner = CronRunner(interval_seconds=0.05, callback=callback)
    runner.start()
    time.sleep(0.18)
    runner.stop()
    assert callback.call_count >= 2


def test_cron_runner_stops_cleanly():
    callback = MagicMock()
    runner = CronRunner(interval_seconds=0.05, callback=callback)
    runner.start()
    time.sleep(0.08)
    runner.stop()
    count_at_stop = callback.call_count
    time.sleep(0.15)
    # Should not have called again after stop
    assert callback.call_count == count_at_stop


def test_cron_runner_logs_callback_exceptions_without_crashing():
    def bad_callback():
        raise RuntimeError("simulated failure")

    runner = CronRunner(interval_seconds=0.05, callback=bad_callback)
    runner.start()
    time.sleep(0.15)
    runner.stop()
    # Should not raise — runner survives callback errors
```

- [ ] **Step 2: Run to verify they fail**

```powershell
python -m pytest tests/runner/test_cron_runner.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Write `runner/scheduler/cron_runner.py`**

```python
# runner/scheduler/cron_runner.py
"""
Dev-mode cron runner. Runs the callback on a fixed interval in a background thread.
Use instead of Windows Task Scheduler during development and testing.

Usage:
    from runner.main import run_cycle
    from runner.scheduler.cron_runner import CronRunner

    runner = CronRunner(interval_seconds=3600, callback=run_cycle)
    runner.start()
    # Ctrl-C to stop
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        runner.stop()
"""
import logging
import threading
import time
from typing import Callable

log = logging.getLogger(__name__)


class CronRunner:
    def __init__(self, interval_seconds: float, callback: Callable[[], None]):
        self._interval = interval_seconds
        self._callback = callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._interval + 1)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._callback()
            except Exception as exc:
                log.error("CronRunner callback error: %s", exc)
            self._stop_event.wait(timeout=self._interval)
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_cron_runner.py -v --tb=short
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\scheduler\cron_runner.py tests\runner\test_cron_runner.py
git commit -m "feat: add dev-mode cron runner for testing without Windows Task Scheduler"
```

---

## Task 4: .gitignore

**Files:**
- Create: `.gitignore`

No tests needed — verified by running `git status`.

- [ ] **Step 1: Create `.gitignore`**

```gitignore
# Python bytecode
__pycache__/
*.py[cod]
*.pyo

# Virtual environments
.venv/
venv/
env/

# Environment / secrets
.env
.env.*
*.key
config/secrets.yaml

# Editor
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Test artifacts
.pytest_cache/
.coverage
htmlcov/

# Generated assets (large files, not source)
workspace/assets/images/*.png
workspace/assets/images/*.jpg
workspace/assets/audio/*.mp3
workspace/assets/audio/*.wav

# Ledger data (runtime, not source)
workspace/ledger/
workspace/logs/
workspace/locks/
```

- [ ] **Step 2: Verify git status looks clean**

```powershell
git status
```

Expected: Only `.gitignore` shows as new. `__pycache__` directories no longer shown as untracked.

- [ ] **Step 3: Commit**

```powershell
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

## Final: Full Test Suite

- [ ] **Run all tests**

```powershell
python -m pytest tests/ -v --tb=short
```

Expected: All PASSED. Count will be 78 + 5 (level_check) + 3 (cron_runner) = 86 passed.

---

## What's Complete After This Plan

The full AI Operations Command Center ecosystem is live:

| Component | Status |
|---|---|
| Agent Runner (11 agents) | ✅ |
| All 11 agent personas | ✅ |
| Tool adapters (5 tools) | ✅ |
| Budget enforcement (Ledger) | ✅ |
| Automation level gating | ✅ |
| Dashboard (FastAPI + WebSocket) | ✅ |
| Tony Stocks bridge | ✅ |
| Plugin skill injection | ✅ |
| Windows Task Scheduler setup | ✅ |
| Dev-mode cron runner | ✅ |
| .gitignore | ✅ |
