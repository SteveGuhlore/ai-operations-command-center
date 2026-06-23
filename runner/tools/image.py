import base64
import httpx
import openai
from pathlib import Path

from runner.llm_switch import llm_disabled

OUTPUT_DIR = Path(__file__).parent.parent.parent / "workspace" / "assets" / "images"

# gpt-image-1 supported sizes
SIZES = {
    "square": "1024x1024",
    "portrait": "1024x1536",  # vertical — use for TikTok/Reels backgrounds
    "landscape": "1536x1024",
    # Legacy aliases mapped to nearest gpt-image-1 equivalent
    "1024x1024": "1024x1024",
    "1024x1792": "1024x1536",  # remapped
    "1792x1024": "1536x1024",  # remapped
    "1024x1536": "1024x1536",
    "1536x1024": "1536x1024",
}


def generate_image(prompt: str, filename: str, size: str = "1024x1024") -> dict:
    if llm_disabled():
        return {"error": "image generation skipped — CC_LLM_DISABLED"}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = openai.OpenAI()
    resolved_size = SIZES.get(size, "1024x1024")
    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size=resolved_size,
        )
        raw = response.data[0]
        if getattr(raw, "b64_json", None):
            image_data = base64.b64decode(raw.b64_json)
        else:
            image_data = httpx.get(raw.url, timeout=60).content

        out_path = OUTPUT_DIR / filename
        out_path.write_bytes(image_data)
        return {
            "success": True,
            "path": str(out_path),
            "prompt": prompt,
            "size": resolved_size,
        }
    except Exception as exc:
        return {"error": str(exc), "prompt": prompt}


def image_generation(prompt: str, filename: str, size: str = "1024x1024") -> dict:
    return generate_image(prompt, filename, size)


TOOL_SPEC = {
    "name": "image_generation",
    "description": (
        "Generate an image using gpt-image-1 and save it to workspace/assets/images/. "
        "Use size 'portrait' or '1024x1536' for vertical video backgrounds (TikTok, Reels, Shorts). "
        "Do NOT include text or words in prompts for video backgrounds."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed image generation prompt. For video backgrounds: no text or words in the image.",
            },
            "filename": {
                "type": "string",
                "description": "Output filename, e.g. POD-SOC-003-bg-1.png",
            },
            "size": {
                "type": "string",
                "enum": [
                    "1024x1024",
                    "1024x1536",
                    "1536x1024",
                    "portrait",
                    "landscape",
                    "square",
                ],
                "default": "1024x1024",
                "description": "Use 'portrait' or '1024x1536' for vertical 9:16 video backgrounds.",
            },
        },
        "required": ["prompt", "filename"],
    },
}
