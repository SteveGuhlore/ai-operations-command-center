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
