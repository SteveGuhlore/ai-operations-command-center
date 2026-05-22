from typing import Any, Callable

TOOL_REGISTRY: dict[str, Callable] = {}


def register_tool(name: str, adapter: Callable) -> None:
    TOOL_REGISTRY[name] = adapter


def dispatch_tool(tool_name: str, tool_input: dict) -> Any:
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")
    try:
        return TOOL_REGISTRY[tool_name](**tool_input)
    except Exception as exc:
        return {"error": str(exc)}


# Auto-register built-in tools at import time
from runner.tools.files import file_editor
from runner.tools.web import web_research
from runner.tools.code import code_runner
from runner.tools.image import image_generation
from runner.tools.audio import audio_generation
from runner.tools.etsy import etsy_listing
from runner.tools.social import save_video_package, post_to_instagram, post_to_facebook, post_to_youtube
from runner.tools.video import assemble_video

register_tool("file_editor",        file_editor)
register_tool("web_research",       web_research)
register_tool("code_runner",        code_runner)
register_tool("image_generation",   image_generation)
register_tool("audio_generation",   audio_generation)
register_tool("etsy_listing",       etsy_listing)
register_tool("save_video_package", save_video_package)
register_tool("post_to_instagram",  post_to_instagram)
register_tool("post_to_facebook",   post_to_facebook)
register_tool("post_to_youtube",    post_to_youtube)
register_tool("assemble_video",     assemble_video)
