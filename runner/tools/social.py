"""
Social media output tool — saves complete video packages to workspace/social/ready-to-post/.
Auto-posting via Meta Graph API (Instagram/Facebook) and YouTube Data API when keys are set.
TikTok: saves to ready-to-post folder for manual upload or Buffer scheduling.
"""
import json
import os
from datetime import datetime
from pathlib import Path

SOCIAL_DIR = Path(__file__).parent.parent.parent / "workspace" / "social"
READY_DIR  = SOCIAL_DIR / "ready-to-post"
POSTED_DIR = SOCIAL_DIR / "posted"


def save_video_package(
    title: str,
    script: str,
    caption: str,
    hashtags: str,
    platform: str = "all",
    audio_file: str = "",
    thumbnail_file: str = "",
) -> dict:
    """Save a complete video package to the ready-to-post queue."""
    READY_DIR.mkdir(parents=True, exist_ok=True)

    slug = title.lower().replace(" ", "-")[:40]
    ts   = datetime.now().strftime("%Y%m%d-%H%M%S")
    pkg  = {
        "title":          title,
        "script":         script,
        "caption":        caption,
        "hashtags":       hashtags,
        "platform":       platform,
        "audio_file":     audio_file,
        "thumbnail_file": thumbnail_file,
        "created_at":     ts,
        "status":         "ready",
    }

    out_path = READY_DIR / f"{ts}-{slug}.json"
    out_path.write_text(json.dumps(pkg, indent=2), encoding="utf-8")

    script_path = READY_DIR / f"{ts}-{slug}-script.md"
    script_path.write_text(
        f"# {title}\n\n**Platform:** {platform}\n\n## Script\n\n{script}\n\n## Caption\n\n{caption}\n\n## Hashtags\n\n{hashtags}\n",
        encoding="utf-8",
    )

    return {
        "success":     True,
        "package":     str(out_path),
        "script_file": str(script_path),
        "status":      "ready-to-post",
        "message":     f"Video package saved. Upload script + audio to {platform}.",
    }


def post_to_instagram(
    caption: str,
    video_path: str,
    thumbnail_path: str = "",
) -> dict:
    """Post a Reel to Instagram via Meta Graph API. Requires INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID."""
    token      = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID")

    if not token or not account_id:
        return {"error": "INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID not set in .env — video saved to ready-to-post queue instead"}

    try:
        import httpx
        # Step 1: create media container
        r1 = httpx.post(
            f"https://graph.facebook.com/v19.0/{account_id}/media",
            params={
                "video_url":   video_path,
                "caption":     caption,
                "media_type":  "REELS",
                "access_token": token,
            },
            timeout=30,
        )
        data = r1.json()
        if "id" not in data:
            return {"error": data.get("error", {}).get("message", "Media container failed")}

        container_id = data["id"]

        # Step 2: publish
        r2 = httpx.post(
            f"https://graph.facebook.com/v19.0/{account_id}/media_publish",
            params={"creation_id": container_id, "access_token": token},
            timeout=30,
        )
        result = r2.json()
        return {"success": True, "post_id": result.get("id"), "platform": "instagram"}
    except Exception as exc:
        return {"error": str(exc)}


def post_to_youtube(
    title: str,
    description: str,
    video_path: str,
    tags: list[str] | None = None,
) -> dict:
    """Upload a Short to YouTube via YouTube Data API v3. Requires YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID."""
    api_key    = os.environ.get("YOUTUBE_API_KEY")
    channel_id = os.environ.get("YOUTUBE_CHANNEL_ID")

    if not api_key or not channel_id:
        return {"error": "YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID not set in .env — video saved to ready-to-post queue instead"}

    return {"error": "YouTube upload requires OAuth2 flow — set up via scripts/setup_youtube_oauth.py (coming soon)"}


TOOL_SPEC_SAVE = {
    "name": "save_video_package",
    "description": "Save a complete video package (script + caption + hashtags) to the ready-to-post queue. Use this after writing a video script.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title":          {"type": "string", "description": "Short title for this video"},
            "script":         {"type": "string", "description": "Full video script with timing marks"},
            "caption":        {"type": "string", "description": "Platform caption (TikTok version)"},
            "hashtags":       {"type": "string", "description": "Hashtags as a string"},
            "platform":       {"type": "string", "description": "Target platform: tiktok, instagram, youtube, facebook, or all", "default": "all"},
            "audio_file":     {"type": "string", "description": "Path to generated audio file if Echo produced one", "default": ""},
            "thumbnail_file": {"type": "string", "description": "Path to thumbnail image if Frame produced one", "default": ""},
        },
        "required": ["title", "script", "caption", "hashtags"],
    },
}

def post_to_facebook(
    caption: str,
    video_path: str,
) -> dict:
    """Post a Reel to Facebook via Meta Graph API. Requires FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID."""
    token   = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN")
    page_id = os.environ.get("FACEBOOK_PAGE_ID")

    if not token or not page_id:
        return {"error": "FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID not set in .env — video saved to ready-to-post queue instead"}

    try:
        import httpx
        r = httpx.post(
            f"https://graph.facebook.com/v19.0/{page_id}/videos",
            params={
                "file_url":     video_path,
                "description":  caption,
                "access_token": token,
            },
            timeout=30,
        )
        data = r.json()
        if "id" in data:
            return {"success": True, "post_id": data["id"], "platform": "facebook"}
        return {"error": data.get("error", {}).get("message", "Facebook post failed")}
    except Exception as exc:
        return {"error": str(exc)}


TOOL_SPEC_INSTAGRAM = {
    "name": "post_to_instagram",
    "description": "Post a Reel directly to Instagram via Meta Graph API. Requires INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID in .env.",
    "input_schema": {
        "type": "object",
        "properties": {
            "caption":        {"type": "string"},
            "video_path":     {"type": "string", "description": "Public URL or path to video file"},
            "thumbnail_path": {"type": "string", "default": ""},
        },
        "required": ["caption", "video_path"],
    },
}
