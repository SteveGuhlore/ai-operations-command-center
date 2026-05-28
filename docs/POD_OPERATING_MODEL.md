# Pod Operating Model

## Goal

Explain how revenue pods should operate within the generic AI Operations Command Center.

## Layers

1. Core command center:
   task state, locks, logs, reports, validation, approvals
2. Core agents:
   reusable workers — Atlas, Forge, Scout, Muse, Frame, Echo, Guard, Ledger, **Maker**, **Market**
3. Revenue pods:
   business units that combine agents and tools into revenue workflows

## How pods use agents

A pod does not replace the agent system. It selects from the shared agent pool based on business needs.

**Market** is assigned across pods as the central marketer: listings, hooks, launch plans, campaigns, repurposing, and offer improvement.

**Maker** is the digital product specialist for build-heavy assets (guides, templates, checklists, SOPs, mini ebooks).

Example combinations:

- **digital products pod:** Maker (asset) → Market (positioning & launch) → Muse/Frame (supporting copy/media) → Guard → Ledger
- **Etsy / dropshipping pods:** Muse/Frame (assets) → **Market** (listings & offers) → Guard → Ledger
- **affiliate / lead gen pods:** Muse (content) → **Market** (funnels, hooks, sequences) → Guard → Ledger
- **short-form video pod:** Frame/Echo/Muse → **Market** (campaign hooks & distribution plan) → Guard → Ledger
- **stock research pod:** Tony Stocks (optional research) → **Market** (newsletter/audience packaging) → Guard → Ledger
- **app/SaaS pod:** Forge/Scout (product) → Muse → **Market** (positioning & pricing narrative) → Guard → Ledger

## Maker vs Market

| | Maker | Market |
|---|--------|--------|
| **role_id** | `digital_product_worker` | `marketing_worker` |
| **Focus** | Product research and asset creation | Go-to-market for all agents and pods |
| **Typical output** | PDF outline, template pack, SOP, checklist | Launch plan, listing strategy, hooks, campaign brief |
| **Relationship** | Feeds Market; not the only input to Market | Consumes Maker, Muse, Frame, Echo, Forge, Tony Stocks, pod outputs |

## Pod boundaries

Every pod should define:

- allowed task types
- forbidden task types
- required tools
- approval points
- success metrics
- risk notes
- first safe tasks

## First safe tasks

Pods should start with safe, internal work such as:

- briefs
- summaries
- prompts
- reports
- outlines
- templates
- asset planning
- **marketing handoff packages** (Market)
- **product outlines** (Maker)

They should not begin with live external actions.

## Approval model

Human approval remains required for:

- publishing
- spending above budget
- purchases
- account connections
- production release
- real-money or real-account decisions
- paid campaign launch

## Metrics model

Each pod should track simple metrics first:

- outputs prepared
- approved assets ready
- workflows documented
- risks reduced
- offers and launch materials drafted (Market)
- product concepts ready (Maker)

Only later should it expand into live performance metrics.

## Template source

- [revenue-pod-task.md](../task_templates/revenue-pod-task.md) — pod-specific work items
- [digital-product-task.md](../task_templates/digital-product-task.md) — Maker product builds
- [marketing-handoff-task.md](../task_templates/marketing-handoff-task.md) — Market packaging from any upstream agent
