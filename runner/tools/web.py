import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def web_search(query: str) -> dict:
    client = _get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": f"Search the web for: {query}. Summarise the top results briefly."}],
    )
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
    return {"content": text, "query": query}


def web_fetch(url: str) -> dict:
    client = _get_client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": f"Fetch and summarise the content at this URL: {url}"}],
    )
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
    return {"content": text, "url": url}


def web_research(action: str, query: str = "", url: str = "") -> dict:
    if action == "search":
        return web_search(query)
    if action == "fetch":
        return web_fetch(url)
    return {"error": f"Unknown action: {action}"}


TOOL_SPEC = {
    "name": "web_research",
    "description": "Search the web or fetch a URL for current information.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search", "fetch"]},
            "query": {"type": "string", "description": "Search query (for search action)"},
            "url": {"type": "string", "description": "URL to fetch (for fetch action)"},
        },
        "required": ["action"],
    }
}
