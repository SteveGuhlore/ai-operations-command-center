import os
import time
import random
import httpx
from html.parser import HTMLParser
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

_DDG_URL = "https://html.duckduckgo.com/html/"

# Rotating User-Agents to avoid detection
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/131.0.2903.86",
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8",
    "en-CA,en;q=0.9,fr;q=0.8",
    "en-AU,en;q=0.9",
]

_BLOCKED_HOSTS = (
    "yelp.com", "google.com", "facebook.com",
    "instagram.com", "linkedin.com", "tripadvisor.com",
)

# API Keys
_BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
_GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
_GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
_SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
_SCRAPINGBEE_KEY = os.getenv("SCRAPINGBEE_KEY", "")
_BING_API_KEY = os.getenv("BING_API_KEY", "")

# API Endpoints
_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
_SERPAPI_URL = "https://serpapi.com/search"
_BING_URL = "https://api.bing.microsoft.com/v7.0/search"
_SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1"

# =============================================================================
# HTML PARSER
# =============================================================================

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = False
        self._in_result = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True
        # DuckDuckGo result containers
        if tag in ("div", "a"):
            attrs_dict = dict(attrs)
            if attrs_dict.get("class", "").startswith("result"):
                self._in_result = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


# =============================================================================
# CAPTCHA DETECTION
# =============================================================================

def _is_captcha_response(text: str) -> bool:
    """Detect common CAPTCHA challenge indicators in response."""
    if not text:
        return True  # Empty response is suspicious
    
    captcha_indicators = [
        "captcha", "CAPTCHA", "recaptcha", "reCAPTCHA",
        "please verify", "verifying you are human",
        "i'm not a robot", "i am not a robot",
        "security check", "cloudflare",
        "please enable javascript", "enable javascript",
        "bot detection", "bot check",
        "too many requests", "rate limit",
        "verify you are human", "human verification",
        "ddos protection", "access denied",
        "blocked", "your ip has been blocked",
        "suspicious activity", "unusual traffic",
    ]
    text_lower = text.lower()
    return any(indicator.lower() in text_lower for indicator in captcha_indicators)


def _is_valid_search_result(text: str) -> bool:
    """Check if response contains actual search results."""
    if not text or len(text) < 100:
        return False
    
    result_indicators = [
        "result", "results", "search", "found",
        "http", "www.", ".com", ".org", ".net",
    ]
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in result_indicators)


# =============================================================================
# REQUEST HELPERS
# =============================================================================

def _get_random_headers() -> dict:
    """Generate randomized headers to avoid detection."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def _exponential_delay(attempt: int, base_delay: float = 1.0) -> None:
    """Apply exponential backoff with jitter."""
    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
    time.sleep(min(delay, 10))  # Cap at 10 seconds


# =============================================================================
# CONTACT EXTRACTION
# =============================================================================

_IG_STOPWORDS = {
    "instagram", "contact", "email", "support", "info", "the", "and",
    "for", "with", "https", "http", "www", "com", "please", "photos",
    "videos", "posts", "reels", "stories", "explore", "share", "follow",
    "followers", "following", "like", "likes", "tag", "tagged", "ans",
    "p", "tv", "accounts", "login", "signup", "about", "help",
    "privacy", "terms", "careers", "press", "blog",
}


def _extract_business_contact_info(text: str, query: str = "", sources: list | None = None) -> dict:
    """Extract emails, phone numbers, and social media handles."""
    import re

    # Extract emails
    email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
    emails = re.findall(email_pattern, text)
    filtered_emails = []
    seen_emails = set()
    for e in emails:
        e = e.strip().rstrip(",.;:")
        low = e.lower()
        if low in seen_emails:
            continue
        if any(x in low for x in ["example.com", "domain.com", "email.com", "user@", "@2x", "@3x", "sentry.io", "wixpress.com"]):
            continue
        seen_emails.add(low)
        filtered_emails.append(e)

    # Extract phone numbers (US formats)
    phone_pattern = r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
    phones = re.findall(phone_pattern, text)
    formatted_phones = [f"({p[0]}) {p[1]}-{p[2]}" for p in phones]

    # Extract Instagram handles
    handles_ranked: list[tuple[int, str]] = []
    seen_handles = set()

    def _add(handle: str, score: int) -> None:
        h = handle.strip("_.@").lower()
        if not (3 <= len(h) <= 30) or h in _IG_STOPWORDS or h in seen_handles:
            return
        seen_handles.add(h)
        handles_ranked.append((score, f"@{h}"))

    # Instagram URLs (highest confidence)
    url_pattern = r'(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9_.]{3,30})/?'
    for src in (sources or []):
        for m in re.findall(url_pattern, src or "", re.IGNORECASE):
            _add(m, score=100)
    for m in re.findall(url_pattern, text, re.IGNORECASE):
        _add(m, score=80)

    # Parenthesized handles
    paren_pattern = r'\(@([A-Za-z0-9_.]{3,30})\)'
    for m in re.findall(paren_pattern, text):
        _add(m, score=60)

    # Labeled handles
    labeled_pattern = r'(?:instagram|ig)[:\s]+@?([A-Za-z0-9_.]{3,30})'
    for m in re.findall(labeled_pattern, text, re.IGNORECASE):
        _add(m, score=40)

    handles_ranked.sort(key=lambda t: -t[0])
    unique_handles = [h for _, h in handles_ranked][:3]

    # Extract Facebook pages
    fb_pattern = r'(?:https?://)?(?:www\.)?facebook\.com/([A-Za-z0-9.]{3,50})/?'
    facebook_pages = list(set(re.findall(fb_pattern, text, re.IGNORECASE)))[:2]

    # Extract LinkedIn profiles
    li_pattern = r'(?:https?://)?(?:www\.)?linkedin\.com/(?:in|company)/([A-Za-z0-9-]{3,100})/?'
    linkedin_profiles = list(set(re.findall(li_pattern, text, re.IGNORECASE)))[:2]

    return {
        "emails": filtered_emails[:3],
        "phones": formatted_phones[:2],
        "instagram_handles": unique_handles,
        "facebook_pages": facebook_pages,
        "linkedin_profiles": linkedin_profiles,
        "raw_text": text[:2000],
    }


# =============================================================================
# SEARCH PROVIDERS
# =============================================================================

def _serpapi_search(query: str) -> Optional[dict]:
    """Search via SerpAPI - handles Google searches without CAPTCHA issues."""
    if not _SERPAPI_KEY:
        return None

    params = {
        "engine": "google",
        "q": query,
        "api_key": _SERPAPI_KEY,
        "num": 10,
        "gl": "us",
        "hl": "en",
    }

    try:
        resp = httpx.get(_SERPAPI_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            return {"content": "", "error": data["error"], "sources": []}

        results = data.get("organic_results", [])
        parts = []
        sources = []

        for r in results:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            url = r.get("link", "")
            if title or snippet:
                parts.append(f"{title}: {snippet}")
                sources.append(url)

        content = " ".join(parts)[:3000]
        return {"content": content, "sources": sources, "provider": "serpapi"}

    except Exception as exc:
        return {"content": "", "error": str(exc), "sources": []}


def _brave_search(query: str) -> Optional[dict]:
    """Search via Brave Search API - reliable, no CAPTCHA."""
    if not _BRAVE_API_KEY:
        return None

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": _BRAVE_API_KEY,
    }
    params = {"q": query, "count": 10, "search_lang": "en", "extra_snippets": 1}

    try:
        resp = httpx.get(_BRAVE_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("web", {}).get("results", [])
        parts = []
        sources = []

        for r in results:
            title = r.get("title", "")
            desc = r.get("description", "")
            url = r.get("url", "")
            if title or desc:
                parts.append(f"{title}: {desc}")
                sources.append(url)

        content = " ".join(parts)[:3000]
        return {"content": content, "sources": sources, "provider": "brave"}

    except Exception as exc:
        return {"content": "", "error": str(exc), "sources": []}


def _bing_search(query: str) -> Optional[dict]:
    """Search via Bing Search API."""
    if not _BING_API_KEY:
        return None

    headers = {"Ocp-Apim-Subscription-Key": _BING_API_KEY}
    params = {"q": query, "count": 10, "mkt": "en-US"}

    try:
        resp = httpx.get(_BING_URL, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        web_pages = data.get("webPages", {}).get("value", [])
        parts = []
        sources = []

        for page in web_pages:
            name = page.get("name", "")
            snippet = page.get("snippet", "")
            url = page.get("url", "")
            if name or snippet:
                parts.append(f"{name}: {snippet}")
                sources.append(url)

        content = " ".join(parts)[:3000]
        return {"content": content, "sources": sources, "provider": "bing"}

    except Exception as exc:
        return {"content": "", "error": str(exc), "sources": []}


def _google_custom_search(query: str) -> Optional[dict]:
    """Search via Google Custom Search API."""
    if not _GOOGLE_CSE_API_KEY or not _GOOGLE_CSE_ID:
        return None

    params = {
        "key": _GOOGLE_CSE_API_KEY,
        "cx": _GOOGLE_CSE_ID,
        "q": query,
        "num": 10,
    }

    try:
        resp = httpx.get(_GOOGLE_CSE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            return {"content": "", "error": data["error"]["message"], "sources": []}

        items = data.get("items", [])
        parts = []
        sources = []

        for item in items:
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            if title or snippet:
                parts.append(f"{title}: {snippet}")
                sources.append(link)

        content = " ".join(parts)[:3000]
        return {"content": content, "sources": sources, "provider": "google_cse"}

    except Exception as exc:
        return {"content": "", "error": str(exc), "sources": []}


def _duckduckgo_search(query: str, max_retries: int = 3) -> Optional[dict]:
    """Search via DuckDuckGo with CAPTCHA detection and retry logic."""
    for attempt in range(max_retries):
        try:
            # Add delay between retries
            if attempt > 0:
                _exponential_delay(attempt - 1)

            headers = _get_random_headers()
            
            # Use alternative DDG endpoints
            if attempt == 0:
                url = _DDG_URL
            elif attempt == 1:
                url = "https://lite.duckduckgo.com/lite/"
            else:
                url = "https://duckduckgo.com/html/"

            resp = httpx.post(
                url,
                data={"q": query, "kl": "us-en"},
                headers=headers,
                timeout=20,
                follow_redirects=True,
            )
            resp.raise_for_status()

            # Check for CAPTCHA
            if _is_captcha_response(resp.text):
                if attempt < max_retries - 1:
                    continue
                return {"content": "", "error": "CAPTCHA detected", "captcha_blocked": True, "sources": []}

            # Extract text
            extractor = _TextExtractor()
            extractor.feed(resp.text)
            text = " ".join(extractor.parts)[:4000]

            # Validate results
            if not _is_valid_search_result(text):
                if attempt < max_retries - 1:
                    continue
                return {"content": "", "error": "Invalid or empty results", "sources": []}

            return {"content": text, "sources": [], "provider": "duckduckgo"}

        except Exception as exc:
            if attempt < max_retries - 1:
                continue
            return {"content": "", "error": str(exc), "sources": []}

    return {"content": "", "error": "Max retries exceeded", "sources": []}


def _scrapingbee_search(query: str) -> Optional[dict]:
    """Search via ScrapingBee (proxy service) for hard-to-scrape sites."""
    if not _SCRAPINGBEE_KEY:
        return None

    search_url = f"https://html.duckduckgo.com/html/?q={httpx.URL(query).raw_path}"
    
    params = {
        "api_key": _SCRAPINGBEE_KEY,
        "url": search_url,
        "render_js": "false",
        "premium_proxy": "true",
    }

    try:
        resp = httpx.get(_SCRAPINGBEE_URL, params=params, timeout=30)
        resp.raise_for_status()

        if _is_captcha_response(resp.text):
            return {"content": "", "error": "CAPTCHA even with proxy", "captcha_blocked": True, "sources": []}

        extractor = _TextExtractor()
        extractor.feed(resp.text)
        text = " ".join(extractor.parts)[:4000]

        return {"content": text, "sources": [], "provider": "scrapingbee"}

    except Exception as exc:
        return {"content": "", "error": str(exc), "sources": []}


# =============================================================================
# MAIN SEARCH FUNCTION
# =============================================================================

def web_search(query: str) -> dict:
    """
    Search the web with robust CAPTCHA handling.
    
    Strategy (in order of preference):
    1. SerpAPI (if configured) - handles Google without CAPTCHA
    2. Brave Search API - reliable, fast
    3. Bing Search API - Microsoft alternative
    4. Google Custom Search - Google results via API
    5. ScrapingBee proxy (if configured)
    6. DuckDuckGo with retry logic
    
    For contact queries, extracts structured contact information.
    """
    errors = []
    is_contact_query = any(k in query.lower() for k in ("contact", "email", "instagram", "facebook", "phone", "yelp"))

    # Provider chain in order of reliability
    providers = [
        ("serpapi", _serpapi_search),
        ("brave", _brave_search),
        ("bing", _bing_search),
        ("google_cse", _google_custom_search),
        ("scrapingbee", _scrapingbee_search),
        ("duckduckgo", _duckduckgo_search),
    ]

    for provider_name, provider_func in providers:
        try:
            result = provider_func(query)
            
            # Skip if provider not configured or returned None
            if result is None:
                continue
            
            # Check for errors
            if result.get("error"):
                errors.append(f"{provider_name}: {result['error']}")
                # If CAPTCHA blocked, continue to next provider
                if result.get("captcha_blocked"):
                    continue
                # For other errors, still try next provider
                continue
            
            # Success - process result
            content = result.get("content", "")
            sources = result.get("sources", [])
            provider = result.get("provider", provider_name)

            # Extract contact info if contact query
            if is_contact_query:
                contact_info = _extract_business_contact_info(content, query, sources)
                
                # Add contact summary to content
                summary_lines = []
                if contact_info["emails"]:
                    summary_lines.append("CONTACT FOUND — Email: " + ", ".join(contact_info["emails"]))
                if contact_info["phones"]:
                    summary_lines.append("CONTACT FOUND — Phone: " + ", ".join(contact_info["phones"]))
                if contact_info["instagram_handles"]:
                    summary_lines.append("CONTACT FOUND — Instagram: " + ", ".join(contact_info["instagram_handles"]))
                if contact_info["facebook_pages"]:
                    summary_lines.append("CONTACT FOUND — Facebook: " + ", ".join(contact_info["facebook_pages"]))
                
                if summary_lines:
                    content = "\n".join(summary_lines) + "\n\n" + content

                return {
                    "content": content,
                    "query": query,
                    "structured": contact_info,
                    "sources": sources,
                    "provider": provider,
                    "success": True,
                }

            return {
                "content": content,
                "query": query,
                "sources": sources,
                "provider": provider,
                "success": True,
            }

        except Exception as exc:
            errors.append(f"{provider_name}: {str(exc)}")
            continue

    # All providers failed
    if is_contact_query:
        return {
            "content": "All search providers failed. Unable to retrieve contact information.",
            "query": query,
            "captcha_blocked": True,
            "structured": {"emails": [], "phones": [], "instagram_handles": [], "facebook_pages": [], "linkedin_profiles": []},
            "error": "; ".join(errors) if errors else "All search strategies exhausted",
            "success": False,
        }

    return {
        "content": "",
        "query": query,
        "error": "; ".join(errors) if errors else "All search strategies exhausted",
        "success": False,
    }


def web_fetch(url: str, max_retries: int = 2) -> dict:
    """Fetch and parse a URL with CAPTCHA detection and retry logic."""
    
    # Check blocked hosts
    if any(host in url.lower() for host in _BLOCKED_HOSTS):
        return {
            "content": "",
            "url": url,
            "captcha_blocked": True,
            "error": f"Skipped — {url} host blocks bots. Use web_search snippets instead.",
        }

    # Try ScrapingBee first if available
    if _SCRAPINGBEE_KEY:
        try:
            params = {
                "api_key": _SCRAPINGBEE_KEY,
                "url": url,
                "render_js": "false",
                "premium_proxy": "true",
            }
            resp = httpx.get(_SCRAPINGBEE_URL, params=params, timeout=30)
            resp.raise_for_status()
            
            if not _is_captcha_response(resp.text):
                extractor = _TextExtractor()
                extractor.feed(resp.text)
                text = " ".join(extractor.parts)[:4000]
                return {"content": text, "url": url, "success": True}
        except Exception:
            pass  # Fall through to direct fetch

    # Direct fetch with retries
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                _exponential_delay(attempt - 1)

            headers = _get_random_headers()
            resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
            resp.raise_for_status()

            if _is_captcha_response(resp.text):
                if attempt < max_retries - 1:
                    continue
                return {
                    "content": "",
                    "url": url,
                    "captcha_blocked": True,
                    "error": "CAPTCHA challenge detected on target page",
                }

            extractor = _TextExtractor()
            extractor.feed(resp.text)
            text = " ".join(extractor.parts)[:4000]
            return {"content": text, "url": url, "success": True}

        except Exception as exc:
            if attempt < max_retries - 1:
                continue
            return {"error": str(exc), "url": url}

    return {"error": "Max retries exceeded", "url": url}


def web_research(action: str, query: str = "", url: str = "") -> dict:
    """
    Search the web or fetch a URL for current information.
    
    Implements multiple fallback strategies for CAPTCHA resilience:
    1. SerpAPI - handles Google searches without CAPTCHA issues
    2. Brave Search API - reliable, fast
    3. Bing Search API - Microsoft alternative
    4. Google Custom Search - Google results via API
    5. ScrapingBee proxy - premium proxy service
    6. DuckDuckGo with enhanced evasion techniques
    
    For contact/email searches, automatically extracts structured data:
    - structured.emails: List of email addresses found
    - structured.phones: List of phone numbers found
    - structured.instagram_handles: List of Instagram handles found
    - structured.facebook_pages: List of Facebook pages found
    - structured.linkedin_profiles: List of LinkedIn profiles found
    - captcha_blocked: True if CAPTCHA was encountered
    - provider: Which search provider succeeded
    - success: Boolean indicating if search succeeded
    """
    if action == "search":
        return web_search(query)
    if action == "fetch":
        return web_fetch(url)
    return {"error": f"Unknown action: {action}", "success": False}


TOOL_SPEC = {
    "name": "web_research",
    "description": "Search the web or fetch a URL for current information. Implements 6-tier CAPTCHA-resistant fallback strategy (SerpAPI, Brave, Bing, Google CSE, ScrapingBee, DuckDuckGo). Extracts structured contact info (emails, phones, Instagram, Facebook, LinkedIn) for business queries.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search", "fetch"]},
            "query": {"type": "string", "description": "Search query (for search action). Use for contact info: '[business name] [city] contact email OR instagram OR phone'"},
            "url": {"type": "string", "description": "URL to fetch (for fetch action)"},
        },
        "required": ["action"],
    }
}
