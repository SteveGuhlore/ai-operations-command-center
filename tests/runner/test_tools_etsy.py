import pytest
from unittest.mock import patch, MagicMock
from runner.tools.etsy import create_draft_listing, TOOL_SPEC


def test_create_draft_listing_posts_to_etsy(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "test-key")
    monkeypatch.setenv("ETSY_SHOP_ID", "12345")

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "listing_id": 999,
        "title": "Test Product",
        "state": "draft",
        "url": "https://www.etsy.com/listing/999",
    }

    with patch("runner.tools.etsy.httpx.post", return_value=mock_response):
        result = create_draft_listing(
            title="Test Product",
            description="A great product.",
            price=9.99,
            tags=["tag1", "tag2"],
        )
        assert result["success"] is True
        assert result["listing_id"] == 999
        assert result["state"] == "draft"


def test_create_draft_listing_returns_error_without_api_key(monkeypatch):
    monkeypatch.delenv("ETSY_API_KEY", raising=False)
    monkeypatch.delenv("ETSY_SHOP_ID", raising=False)
    result = create_draft_listing(title="T", description="D", price=5.0, tags=[])
    assert "error" in result


def test_create_draft_listing_handles_api_error(monkeypatch):
    monkeypatch.setenv("ETSY_API_KEY", "test-key")
    monkeypatch.setenv("ETSY_SHOP_ID", "12345")

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"error": "Forbidden"}

    with patch("runner.tools.etsy.httpx.post", return_value=mock_response):
        result = create_draft_listing(
            title="T", description="D", price=5.0, tags=[]
        )
        assert "error" in result


def test_tool_spec_has_required_fields():
    assert TOOL_SPEC["name"] == "etsy_listing"
    assert "input_schema" in TOOL_SPEC
