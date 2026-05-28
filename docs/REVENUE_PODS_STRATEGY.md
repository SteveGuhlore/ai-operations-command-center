# Revenue Pods Strategy

## Goal

Define a reusable business-unit layer that sits above the core agent pool and turns generic production capabilities into monetizable workflows.

## Core idea

Core agents are reusable production workers. Revenue pods are business units that combine agents, tools, task types, guardrails, and approval gates around a specific monetization model.

**Market** (`marketing_worker`) is the **central marketing and sales strategist across all pods** — not only for digital products. **Maker** (`digital_product_worker`) is the primary product builder for downloadable and template-style offers inside the digital products pod and related workflows.

## Why separate them

Separating agents from pods makes the foundation more reusable:

- agents stay generic
- tools stay generic
- pods define business-specific workflow combinations
- **Market** applies consistent positioning, launch, and campaign logic pod-to-pod
- **Maker** focuses on sellable product assets
- approvals and guardrails can differ by monetization model

## Agent ↔ pod pattern

| Agent | Pod role |
|-------|----------|
| Maker | Builds digital product assets (outlines, guides, templates, SOPs) |
| Market | Offers, listings, hooks, launch plans, repurposing, audience strategy for **every** pod |
| Muse | Raw copy and content drafts |
| Frame / Echo | Media and audio assets |
| Forge | Technical packaging or tooling where needed |
| Tony Stocks | Research inputs (optional); Market packages for newsletter/audience |
| Guard / Ledger | Safety and cost gates on all pods |

## Pod list

- `etsy_store_pod`
- `dropshipping_pod`
- `affiliate_content_pod`
- `short_form_video_pod`
- `digital_products_pod` — primary home for **Maker** + **Market**
- `lead_gen_pod`
- `stock_research_pod` — **Market** packages Tony Stocks research for audiences
- `app_saas_pod`

## Design principle

Each pod should describe:

- what it makes money from
- which agents it needs (include `marketing_worker` for go-to-market work)
- which tools it can use
- what tasks it may perform
- what it must not do
- what still requires human approval
- how success is measured
- what the first safe tasks are

## Safety posture

Revenue pods are planning and workflow definitions only at this stage.

They do not:

- connect APIs
- publish externally
- place real orders
- spend money automatically
- run real workers

Revenue pods must pass configuration validation before they should be used as planning inputs for any future workflow.

## Relationship to the command center

The command center remains the source of truth. Revenue pods are organizational overlays for monetizable workstreams, not execution engines.

## Config source

See [revenue-pods.example.yaml](../config/revenue-pods.example.yaml).
