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
from runner.tools.poc_sandbox import poc_runner
from runner.tools.opportunity import log_opportunity, grade_poc, update_opportunity
from runner.tools.revenue_tool import log_revenue
from runner.tools.image import image_generation
from runner.tools.audio import audio_generation
from runner.tools.etsy import etsy_listing
from runner.tools.social import save_video_package, post_to_instagram, post_to_facebook, post_to_youtube
from runner.tools.video import assemble_video
from runner.tools.task_creator import create_task
from runner.tools.tony_insights import write_tony_insight
from runner.tools.tony_verdict import write_tony_verdict
from runner.tools.stock_data import get_stock_data
from runner.tools.email_sender import send_email
from runner.tools.places import find_prospects
from runner.tools.social_dm import send_instagram_dm
from runner.tools.vault_memory import write_memory
from runner.tools.inbox_reader import read_inbox
from runner.tools.flag_issue import flag_issue

register_tool("file_editor",        file_editor)
register_tool("web_research",       web_research)
register_tool("code_runner",        code_runner)
register_tool("poc_runner",          poc_runner)
register_tool("log_opportunity",     log_opportunity)
register_tool("grade_poc",           grade_poc)
register_tool("update_opportunity",  update_opportunity)
register_tool("log_revenue",         log_revenue)
register_tool("image_generation",   image_generation)
register_tool("audio_generation",   audio_generation)
register_tool("etsy_listing",       etsy_listing)
register_tool("save_video_package", save_video_package)
register_tool("post_to_instagram",  post_to_instagram)
register_tool("post_to_facebook",   post_to_facebook)
register_tool("post_to_youtube",    post_to_youtube)
register_tool("assemble_video",     assemble_video)
register_tool("create_task",        create_task)
register_tool("write_tony_insight", write_tony_insight)
register_tool("write_tony_verdict", write_tony_verdict)
register_tool("get_stock_data",     get_stock_data)
register_tool("send_email",         send_email)
register_tool("find_prospects",     find_prospects)
register_tool("send_instagram_dm",  send_instagram_dm)
register_tool("write_memory",       write_memory)
register_tool("read_inbox",         read_inbox)
register_tool("flag_issue",         flag_issue)

from runner.plugins.loader import load_design_skill
register_tool("load_design_skill",  load_design_skill)
