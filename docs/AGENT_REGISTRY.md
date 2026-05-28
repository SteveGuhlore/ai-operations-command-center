# Agent Registry

## Goal

Document the generic roles available to the AI Command Center without wiring them to specific providers or APIs.

## Core roles

- `manager` / `Atlas`: coordinating reviewer, batch planner, escalation owner.
- `heavy_worker` / `Forge`: heavier implementation worker for larger code and build tasks.
- `debug_worker` / `Scout`: lower-cost validation, debugging, and reporting worker.

## Extended operations roles

- `content_worker` / `Muse`: drafts written content, copy, and publish-ready text packages.
- `media_worker` / `Frame`: handles image and video concepting, prompt iteration, and asset packaging.
- `audio_worker` / `Echo`: prepares audio scripts, prompts, and audio asset planning.
- `guard_worker` / `Guard`: runs moderation, policy, and safety checks before risky actions.
- `budget_worker` / `Ledger`: tracks cost, retries, thresholds, and budget shutdown posture.

## Revenue production roles

- `digital_product_worker` / `Maker`: researches and creates sellable digital products (PDFs, guides, templates, checklists, mini ebooks, SOPs, downloadable resources).
- `marketing_worker` / `Market`: **central marketing and sales strategist for all agents and revenue pods.** Market turns outputs from Maker, Muse, Frame, Echo, Tony Stocks, Forge, and every revenue pod into marketable offers, listings, hooks, positioning, launch plans, audience strategies, and promotional campaigns.

### Market scope (all channels)

Market supports planning and packaging across:

- digital products
- Etsy products and listings
- dropshipping products
- affiliate content
- short-form video campaigns
- lead-gen offers
- stock research and newsletter packaging
- app/SaaS positioning
- content repurposing
- launch strategy
- offer improvement

Market does **not** publish, spend money, place trades, or connect APIs. Handoffs to Guard and human approval remain required for external actions.

### Maker ↔ Market handoff

- **Maker** builds the product asset (structure, research synthesis, long-form quality).
- **Market** packages it for sale (positioning, hooks, listings, campaigns, launch plans).
- Other agents (Muse, Frame, Echo, Forge, Tony Stocks) can also feed **Market** without going through Maker first.

## Optional specialist example

- `market_research_worker` / `Tony Stocks`: disabled-by-default specialist profile for market-research summaries, watchlist review, scanner reporting, paper-trade journal summaries, and research notes. Market packages Tony's research for audiences; Tony does not replace Market.

This specialist is optional, not part of the core required team, and remains disconnected until a future project profile and explicit tool permissions exist.

## Role stability

The role IDs should remain stable in tasks, validation rules, and configuration. Display names make logs and handoffs easier to read, but should not replace the role IDs in automation logic.

## Future mapping

Roles can later be mapped to different model providers and model classes in configuration. Each role has one **primary** model for routine work; **fallback** models are manual emergency overrides only.

See:

- [agents.example.yaml](../config/agents.example.yaml)
- [agent-models.example.yaml](../config/agent-models.example.yaml)
- [MODEL_STRATEGY.md](./MODEL_STRATEGY.md)
