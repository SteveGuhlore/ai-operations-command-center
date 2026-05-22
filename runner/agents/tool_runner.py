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
