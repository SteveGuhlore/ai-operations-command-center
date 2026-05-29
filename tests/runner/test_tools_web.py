import runner.tools.web as web
from runner.tools.web import web_search, web_fetch, TOOL_SPEC


def test_web_search_returns_results(monkeypatch):
    # web_search tries providers in order; stub the first so no network call happens.
    monkeypatch.setattr(
        web, "_serpapi_search",
        lambda q: {"content": "Result 1\nResult 2", "sources": [], "provider": "serpapi"},
    )
    result = web_search(query="python asyncio tutorial")
    assert result.get("success") is True
    assert "content" in result
    assert "Result 1" in result["content"]


def test_web_fetch_returns_content(monkeypatch):
    class FakeResp:
        text = "<html><body>Page content here</body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(web, "_SCRAPINGBEE_KEY", "", raising=False)
    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: FakeResp())
    result = web_fetch(url="https://example.com")
    assert "content" in result
    assert "Page content here" in result["content"]


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "web_research"
    assert "input_schema" in TOOL_SPEC
