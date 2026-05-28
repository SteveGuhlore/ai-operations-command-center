# Model Strategy

## Principles

1. **One primary model per agent** — chosen for efficiency, token usage, and task fit.
2. **Fallback models are emergency-only** — manual override when primary is unavailable; not routine routing or automatic escalation.
3. **Stable role IDs** — `manager`, `marketing_worker`, etc. stay fixed; provider names map in config only.
4. **No API wiring in this repo** — labels describe capability class, not live provider endpoints.

Configuration: [agent-models.example.yaml](../config/agent-models.example.yaml).

## Starting core trio

```text
manager      = Atlas   → codex-class reviewer (primary)
heavy_worker = Forge   → kimi-class builder (primary)
debug_worker = Scout   → minimax-class debugger (primary)
```

## Revenue production pair

```text
digital_product_worker = Maker  → longform-product-class writer (primary)
marketing_worker       = Market → strategic-campaign-class writer (primary)
```

### Maker model fit

- **Primary:** `longform-product-class writer` — long-form structure, research synthesis, product-quality writing.
- **Fallback:** `sonnet-class product writer` — manual emergency only for dense product drafts.
- **Not responsible for:** go-to-market copy, ad hooks, or multi-channel campaigns (Market owns that).

### Market model fit

- **Primary:** `strategic-campaign-class writer` — persuasive writing, positioning, audience analysis, reusable campaign planning.
- **Fallback:** `sonnet-class strategist` — manual emergency only for high-stakes launch or positioning work.
- **Scope:** all agents and all revenue pods; not limited to Maker outputs.

## Extended operations models

| Role ID | Display | Primary model | Fallback (manual only) |
|---------|---------|---------------|-------------------------|
| `content_worker` | Muse | haiku-class writer | sonnet-class writer |
| `media_worker` | Frame | multimodal media model | image-prompt-class model |
| `audio_worker` | Echo | speech-class generator | haiku-class script writer |
| `guard_worker` | Guard | safety-class reviewer | codex-class reviewer |
| `budget_worker` | Ledger | lightweight accounting model | haiku-class summarizer |

## Optional specialist

| Role ID | Display | Primary | Notes |
|---------|---------|---------|-------|
| `market_research_worker` | Tony Stocks | configurable_market_research_model | Disabled by default. Market packages research for audiences. |

## Routing rules

- **Do not** rotate models per task automatically.
- **Do not** use fallback as a “second try” on quality — use retries within the same primary model first.
- **Do** change primary assignment only after evaluation (see [MODEL_EVALUATION_PLAN.md](./MODEL_EVALUATION_PLAN.md)).
- **Do** document any manual fallback override in run logs.

## Escalation (task-level, not model-level)

`debug_worker` gets 2 attempts on validation and debugging tasks.

If still failing:

- escalate to `heavy_worker` for code-level debugging, or
- escalate to `manager` for architecture or risk review.

`heavy_worker` gets 1 implementation attempt plus 1 repair attempt.

If still failing:

- `manager` breaks the task into smaller tasks.

Product and marketing tasks:

- Maker produces the asset → Market packages for channels → Guard reviews → human approves publish.

## Cost control

- Give workers narrow task files.
- Do not paste the whole repo into every prompt.
- Use read-first docs and exact file lists.
- Cap retries per agent config.
- Cap batch size.
- Save summaries in run logs.
- Prefer Maker + Muse at lower tiers for drafts; reserve Market primary for strategy and campaign layers.

## Config-friendly role mapping

Display names (`Atlas`, `Market`, …) are for humans. Automation uses `role_id` only.

Future provider mapping (OpenRouter, etc.) belongs in a separate integration layer — not in task files.
