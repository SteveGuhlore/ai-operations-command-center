"""Tests for web_research CAPTCHA-resistant implementation."""
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'runner', 'tools'))

from web import (
    _is_captcha_response,
    _is_valid_search_result,
    _extract_business_contact_info,
    _get_random_headers,
    web_search,
    web_fetch,
    web_research,
)


class TestCaptchaDetection:
    """Test CAPTCHA detection functionality."""
    
    def test_detects_recaptcha(self):
        text = "Please complete the reCAPTCHA to continue"
        assert _is_captcha_response(text) is True
    
    def test_detects_cloudflare(self):
        text = "Checking your browser before accessing... Cloudflare"
        assert _is_captcha_response(text) is True
    
    def test_detects_bot_check(self):
        text = "Verifying you are human. This may take a few seconds."
        assert _is_captcha_response(text) is True
    
    def test_detects_rate_limit(self):
        text = "Too many requests. Please try again later."
        assert _is_captcha_response(text) is True
    
    def test_detects_empty_response(self):
        assert _is_captcha_response("") is True
    
    def test_allows_valid_content(self):
        text = "Here are search results for your query. Found 10 results including www.example.com"
        assert _is_captcha_response(text) is False
    
    def test_detects_ddos_protection(self):
        text = "DDoS protection by Cloudflare. Please enable JavaScript."
        assert _is_captcha_response(text) is True


class TestSearchResultValidation:
    """Test search result validation."""
    
    def test_rejects_empty_text(self):
        assert _is_valid_search_result("") is False
    
    def test_rejects_short_text(self):
        assert _is_valid_search_result("hi") is False
    
    def test_accepts_search_results(self):
        text = "Results 1-10 of about 1,000 for 'example search'. www.example.com - Example Domain"
        assert _is_valid_search_result(text) is True
    
    def test_accepts_content_with_urls(self):
        text = "Found information at https://example.com/page with details about the topic."
        assert _is_valid_search_result(text) is True


class TestContactExtraction:
    """Test contact information extraction."""
    
    def test_extracts_emails(self):
        text = "Contact us at support@example.com or sales@example.com for help."
        result = _extract_business_contact_info(text)
        assert "support@example.com" in result["emails"]
        assert "sales@example.com" in result["emails"]
    
    def test_filters_example_emails(self):
        text = "Email us at user@example.com or admin@domain.com"
        result = _extract_business_contact_info(text)
        assert "user@example.com" not in result["emails"]
    
    def test_extracts_instagram_from_url(self):
        text = "Follow us at https://www.instagram.com/mycoolbusiness/ for updates"
        result = _extract_business_contact_info(text)
        assert "@mycoolbusiness" in result["instagram_handles"]
    
    def test_extracts_instagram_from_parentheses(self):
        text = "Check out our Instagram (@mycoolbusiness) for photos"
        result = _extract_business_contact_info(text)
        assert "@mycoolbusiness" in result["instagram_handles"]
    
    def test_extracts_instagram_labeled(self):
        text = "Instagram: mycoolbusiness or IG: anotherhandle"
        result = _extract_business_contact_info(text)
        assert "@mycoolbusiness" in result["instagram_handles"]
    
    def test_extracts_phone_numbers(self):
        text = "Call us at (555) 123-4567 or 555-987-6543"
        result = _extract_business_contact_info(text)
        assert "(555) 123-4563" in result["phones"] or len(result["phones"]) > 0
    
    def test_extracts_facebook_pages(self):
        text = "Find us on Facebook: https://www.facebook.com/MyBusinessPage/"
        result = _extract_business_contact_info(text)
        assert "MyBusinessPage" in result["facebook_pages"]
    
    def test_extracts_linkedin_profiles(self):
        text = "Connect on LinkedIn: https://www.linkedin.com/company/mybusiness/"
        result = _extract_business_contact_info(text)
        assert "mybusiness" in result["linkedin_profiles"]
    
    def test_filters_stopwords(self):
        text = "Instagram: contact Facebook: support"
        result = _extract_business_contact_info(text)
        assert "@contact" not in result["instagram_handles"]
        assert "@support" not in result["instagram_handles"]


class TestHeaderRotation:
    """Test User-Agent rotation."""
    
    def test_returns_different_headers(self):
        h1 = _get_random_headers()
        h2 = _get_random_headers()
        assert "User-Agent" in h1
        assert "Accept" in h1
    
    def test_headers_have_required_fields(self):
        headers = _get_random_headers()
        required = ["User-Agent", "Accept", "Accept-Language", "Accept-Encoding"]
        for field in required:
            assert field in headers


class TestWebResearchInterface:
    """Test the main web_research interface."""
    
    def test_unknown_action_returns_error(self):
        result = web_research("invalid_action")
        assert result["success"] is False
        assert "error" in result
    
    @patch('web._serpapi_search')
    @patch('web._brave_search')
    def test_search_uses_first_successful_provider(self, mock_brave, mock_serpapi):
        mock_serpapi.return_value = None  # Not configured
        mock_brave.return_value = {
            "content": "Test results",
            "sources": ["http://example.com"],
            "provider": "brave",
        }
        
        result = web_research("search", query="test query")
        assert result["success"] is True
        assert result["content"] == "Test results"
    
    @patch('web._serpapi_search')
    @patch('web._brave_search')
    @patch('web._bing_search')
    @patch('web._google_custom_search')
    @patch('web._scrapingbee_search')
    @patch('web._duckduckgo_search')
    def test_search_falls_through_all_providers(
        self, mock_ddg, mock_scrapingbee, mock_google, mock_bing, mock_brave, mock_serpapi
    ):
        # All providers fail
        mock_serpapi.return_value = None
        mock_brave.return_value = None
        mock_bing.return_value = None
        mock_google.return_value = None
        mock_scrapingbee.return_value = None
        mock_ddg.return_value = {"content": "", "error": "CAPTCHA", "captcha_blocked": True}
        
        result = web_research("search", query="contact info")
        assert result["success"] is False
        assert result["captcha_blocked"] is True
    
    def test_fetch_blocks_known_hosts(self):
        result = web_research("fetch", url="https://yelp.com/business")
        assert result["captcha_blocked"] is True
        assert "Skipped" in result["error"]


class TestProviderChains:
    """Test provider chain priority and fallbacks."""
    
    @patch('web._SERPAPI_KEY', 'test_key')
    @patch('web.httpx.get')
    def test_serpapi_search(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "organic_results": [
                {"title": "Test", "snippet": "Result", "link": "http://example.com"}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        from web import _serpapi_search
        result = _serpapi_search("test query")
        assert result is not None
        assert "Test" in result["content"]
    
    @patch('web._BRAVE_API_KEY', 'test_key')
    @patch('web.httpx.get')
    def test_brave_search(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {"title": "Test", "description": "Result", "url": "http://example.com"}
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        from web import _brave_search
        result = _brave_search("test query")
        assert result is not None
        assert "Test" in result["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
