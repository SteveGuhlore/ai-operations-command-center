# Tool Registry

## Goal

Describe the generic tool categories the command center may eventually orchestrate, along with role access and approval posture.

## Tool list

- `code_runner`: local command and validation execution.
- `file_editor`: controlled file creation and edits inside the workspace.
- `web_research`: current-information gathering when browsing is explicitly allowed.
- `image_generation`: still-image generation and refinement.
- `audio_generation`: audio generation and refinement.
- `video_generation`: video generation and refinement.
- `social_scheduler`: external posting and scheduling.
- `cost_tracker`: budget and usage observability.
- `moderation_checker`: content and media moderation checks.

## Approval posture

- Low-risk tools can support observability and internal checks.
- Medium-risk tools usually need role restrictions and conditional approval.
- High-risk tools such as external posting or expensive media generation should stay behind explicit approval gates.

## Registry source

See [tools.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\tools.example.yaml) for the config-only example.
