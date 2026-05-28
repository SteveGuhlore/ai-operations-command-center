---
task_id: POD-SOC-003
assigned_agent: social_media_worker
status: todo
priority: high
pod: social_media_pod
task_type: video_production
platforms: [tiktok, instagram, youtube, facebook]
---

# Full Autonomous Video Production — "ChatGPT Prompt That Writes YouTube Titles"

## Goal
Produce a COMPLETE, finished, upload-ready MP4 video. You must complete ALL pipeline steps — script, voiceover, images, video assembly, package save. Do not stop after writing the script.

## Video Brief
- Topic: One specific ChatGPT prompt that writes YouTube titles
- Style: Screen-recording aesthetic (show the prompt being typed/used)
- Duration: 28–35 seconds
- Tone: Energetic, like sharing a clever shortcut with a friend
- Hook must land in under 2 seconds

## Pipeline — complete every step in order:

### Step 1: Write the script
30-second script. Hook in first 2 seconds. Show the exact prompt. End with "follow for more — I've got 100 of these in a pack, link in bio."

### Step 2: Generate voiceover
Call audio_generation:
- text: the script (spoken words only, no stage directions)
- filename: POD-SOC-003-voiceover.mp3
- voice: nova

### Step 3: Generate 4 background images
Call image_generation 4 times. All must be 1024x1792 (portrait). NO text or words in images.
- Image 1: a glowing laptop screen in a dark room, cinematic, blue light, aerial shot
- Image 2: abstract flowing data streams, purple and blue neon, dark background, vertical orientation
- Image 3: a content creator's desk setup, ring light, monitor glow, dark moody lighting
- Image 4: digital brain neural network, glowing nodes, deep space dark background, vertical

### Step 4: Assemble video
Call assemble_video with the audio file and all 4 image paths.

### Step 5: Save package
Call save_video_package with the full script, TikTok caption, and hashtags.

## Caption (TikTok)
"This ChatGPT prompt writes better YouTube titles than I ever could. Saving this for every video I make. Follow for 100 more prompts — link in bio 🔗"

## Hashtags
TikTok: #ChatGPT #YouTubeGrowth #ContentCreator #AItools #ChatGPTtips #YouTubeTips #CreatorHacks
Instagram: #ChatGPT #ContentCreatorTips #AIProductivity #YouTubeShorts #CreatorTools #DigitalMarketing
