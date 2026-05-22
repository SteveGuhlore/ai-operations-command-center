import openai
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "workspace" / "assets" / "audio"


def generate_audio(text: str, filename: str, voice: str = "alloy") -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = openai.OpenAI()
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
        )
        out_path = OUTPUT_DIR / filename
        out_path.write_bytes(response.content)
        return {"success": True, "path": str(out_path)}
    except Exception as exc:
        return {"error": str(exc)}


def audio_generation(text: str, filename: str, voice: str = "alloy") -> dict:
    return generate_audio(text, filename, voice)


TOOL_SPEC = {
    "name": "audio_generation",
    "description": "Generate speech audio using OpenAI TTS and save to workspace/assets/audio/.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "filename": {"type": "string", "description": "Output filename, e.g. intro.mp3"},
            "voice": {
                "type": "string",
                "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                "default": "alloy",
            },
        },
        "required": ["text", "filename"],
    }
}
