import base64
import openai
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "workspace" / "assets" / "images"


def generate_image(prompt: str, filename: str, size: str = "1024x1024") -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = openai.OpenAI()
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=size,
            response_format="b64_json",
        )
        image_data = base64.b64decode(response.data[0].b64_json)
        out_path = OUTPUT_DIR / filename
        out_path.write_bytes(image_data)
        return {"success": True, "path": str(out_path), "prompt": prompt}
    except Exception as exc:
        return {"error": str(exc), "prompt": prompt}


def image_generation(prompt: str, filename: str, size: str = "1024x1024") -> dict:
    return generate_image(prompt, filename, size)


TOOL_SPEC = {
    "name": "image_generation",
    "description": "Generate an image using DALL-E 3 and save it to workspace/assets/images/.",
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Detailed image generation prompt"},
            "filename": {"type": "string", "description": "Output filename, e.g. product-banner.png"},
            "size": {"type": "string", "enum": ["1024x1024", "1792x1024", "1024x1792"], "default": "1024x1024"},
        },
        "required": ["prompt", "filename"],
    }
}
