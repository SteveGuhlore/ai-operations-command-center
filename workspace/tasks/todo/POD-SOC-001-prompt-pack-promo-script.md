---
task_id: POD-SOC-001
assigned_agent: social_media_worker
status: todo
priority: high
pod: social_media_pod
task_type: video_production
platforms: [tiktok, instagram, youtube, facebook]
---

# Video Production — Promo Script for "100 ChatGPT Prompts for Content Creators"

## Product Being Promoted
"100 ChatGPT Prompts for Content Creators" — a PDF prompt pack from ThePromptVaultUS.
Price: $9. Instant digital download. Works with ChatGPT (free), Claude, Gemini.
Covers: video/podcast ideas, scripting, titles, captions, email, SEO descriptions.

## Goal
Write 3 short-form video scripts promoting this prompt pack — one organic (no sell), one soft-sell, one direct product promo. Then call save_video_package for each one.

## Script 1 — Organic (TikTok/Reels, 30s, no direct sell)
Topic: "The ChatGPT prompt that writes my YouTube titles for me"
Hook angle: Show them one specific prompt from the pack in action. Don't mention the product until the very end — just show the value. CTA: "Follow for more AI shortcuts"

## Script 2 — Soft Sell (Instagram Reels / YouTube Shorts, 45s)
Topic: "3 ChatGPT prompts every content creator should be using"
Hook angle: Pain point — "You're using ChatGPT wrong for content creation." Show 3 prompts (from the pack). End CTA: "I put 100 of these in a pack — link in bio"

## Script 3 — Direct Promo (TikTok Shop / Facebook, 30s)
Topic: Direct product ad for the prompt pack
Hook: Lead with the outcome, not the product. "I went from spending 3 hours on content ideas to 20 minutes — here's the exact tool."
CTA: "Grab it — link in bio / TikTok Shop"

## For each script, call save_video_package with:
- title: the script topic
- script: full script with [Xs] timing marks
- caption: TikTok-optimised caption
- hashtags: TikTok hashtags + Instagram hashtags (separate)
- platform: the target platform(s)
