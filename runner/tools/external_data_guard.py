"""external_data_guard — prompt-injection sanitizer for Tony Stocks' external feeds.

Threat model: Tony is an LLM trading agent that reasons over untrusted text from
news APIs, web research, and EDGAR filings to produce a structured verdict that
includes price levels (target / stop) which can reach real paper orders. A poisoned
headline or web-research blob could (a) hijack Tony's reasoning instructions via
prompt injection, or (b) embed a fake price directive that Tony incorporates into
his verdict, propagating a fraudulent level to the order layer.

This module sanitizes every external text string before it is assembled into Tony's
reasoning prompt, replacing toxic spans with bracketed markers and returning an
audit list of what was neutralized. It is pure / deterministic so tests are hermetic.
"""
import logging
import re

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns — loaded once at import
# ---------------------------------------------------------------------------

# Each entry: (compiled_pattern, flag_name, replacement_marker)
# Order matters: more specific patterns first so a single span can only be
# consumed by the first matching rule (re.sub replaces left-to-right).

_OVERRIDE_INSTRUCTION = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?"
    r"|disregard\s+(?:the\s+)?(?:above|previous)(?:\s+\S+){0,3}"
    r"|do\s+not\s+follow(?:\s+\S+){0,4}"
    r"|new\s+instructions?\s*:)",
    re.IGNORECASE,
)

# Role-injection patterns: persona hijacking, special tokens, prompt-leak attempts
_ROLE_MARKER = re.compile(
    r"(?:<\|[^|>]{0,30}\|>"          # <|im_start|> style tokens
    r"|you\s+are\s+now\b"
    r"|(?:^|\b)system\s*:"
    r"|(?:^|\b)assistant\s*:"
    r"|act\s+as\b"
    r"|reveal\s+your\s+(?:system\s+)?prompt)",
    re.IGNORECASE | re.MULTILINE,
)

# Imperative trade-level directives: verb + level-noun + number.
# Only matches when an imperative verb (set/raise/lower/move/use/buy/sell) directly
# governs a price/stop/target noun followed by a numeric value, OR when a standalone
# noun phrase ("stop loss at X", "price target $X") is used as an imperative directive.
# Descriptive sentences ("shares rose to $50", "Goldman raised its price target to $180",
# "stopped declining at $85") do NOT match because they use passive/descriptive verbs or
# lack the governing imperative structure.
_LEVEL_DIRECTIVE = re.compile(
    r"(?:"
    # Branch 1: imperative verb + optional det + level-noun + optional prep + number
    r"(?:set|raise|lower|move|use|place)\s+(?:the\s+|a\s+|your\s+)?(?:stop(?:\s+loss)?|target|price\s+target|limit|entry)\s*(?:at|to|of|@)?\s*[$]?[\d]+(?:[.,]\d+)?"
    # Branch 2: buy/sell + at/to + number (imperative trade instruction)
    r"|(?:buy|sell)\s+(?:at|to|@)\s*[$]?[\d]+(?:[.,]\d+)?"
    # Branch 3: stop [loss] at/to + number — compound imperative; excludes 'stopped' by
    # requiring the bare form 'stop' (not past tense) as the governing verb/noun
    r"|stop\s+(?:loss\s+)?(?:at|to|@)\s*[$]?[\d]+(?:[.,]\d+)?"
    # Branch 4: standalone "price target $X" as a directive — only at sentence start
    # (after punctuation or line start) to avoid matching embedded descriptive use
    r"|(?:^|(?<=[.!?;,\n]))\s*price\s+target\s+[$]?[\d]+(?:[.,]\d+)?"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

# Control characters: ASCII 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F
# (keep 0x09=tab, 0x0A=newline, 0x0D=carriage-return as normal whitespace)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# ---------------------------------------------------------------------------
# Core sanitizer
# ---------------------------------------------------------------------------

def sanitize_text(s, max_len: int = 600) -> tuple:
    """Sanitize a single text string for safe inclusion in Tony's reasoning prompt.

    Returns (clean_text, flags) where flags is a deduplicated list of short strings
    naming each neutralization applied. Never raises.
    """
    try:
        return _sanitize(s, max_len)
    except Exception as exc:
        _log.error("external_data_guard unexpected error: %s", exc)
        safe = str(s)[:max_len] if isinstance(s, str) else ""
        return safe, ["guard_error"]


def _sanitize(s, max_len: int) -> tuple:
    if not isinstance(s, str):
        return "", []

    flags: list[str] = []

    # Strip control characters
    cleaned, n_subs = _CONTROL_CHARS.subn("", s)
    if n_subs:
        flags.append("control_chars")

    # Neutralize override/instruction patterns
    cleaned, n_subs = _OVERRIDE_INSTRUCTION.subn("[filtered]", cleaned)
    if n_subs:
        flags.append("injection:override_instruction")

    # Neutralize role/persona injection patterns
    cleaned, n_subs = _ROLE_MARKER.subn("[filtered]", cleaned)
    if n_subs:
        flags.append("injection:role_marker")

    # Defang imperative trade-level directives
    cleaned, n_subs = _LEVEL_DIRECTIVE.subn("[filtered-level]", cleaned)
    if n_subs:
        flags.append("injection:level_directive")

    # Truncate
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "…"
        flags.append("truncated")

    return cleaned, flags


# ---------------------------------------------------------------------------
# News article sanitizer
# ---------------------------------------------------------------------------

def sanitize_news(articles: list) -> tuple:
    """Sanitize a list of news article dicts from get_stock_news.

    For each article, headline (max 200 chars) and summary (max 400 chars) are
    sanitized; source/url/ts and other keys are coerced to strings untouched.
    Non-dict items are skipped. Returns (clean_articles, all_flags). Never raises.
    """
    try:
        return _sanitize_news(articles)
    except Exception as exc:
        _log.error("sanitize_news unexpected error: %s", exc)
        return [], ["guard_error"]


def _sanitize_news(articles: list) -> tuple:
    if not isinstance(articles, list):
        return [], []

    clean_articles: list[dict] = []
    all_flags: list[str] = []
    seen_flags: set[str] = set()

    for item in articles:
        if not isinstance(item, dict):
            continue

        headline = item.get("headline") or ""
        summary = item.get("summary") or ""

        clean_headline, h_flags = _sanitize(str(headline) if headline is not None else "", 200)
        clean_summary, s_flags = _sanitize(str(summary) if summary is not None else "", 400)

        for f in h_flags + s_flags:
            if f not in seen_flags:
                seen_flags.add(f)
                all_flags.append(f)

        out = dict(item)
        out["headline"] = clean_headline
        out["summary"] = clean_summary
        # Coerce metadata fields to safe strings (leave None as-is for truthiness checks
        # downstream, but ensure no exotic objects slip through)
        for key in ("source", "url", "ts"):
            if key in out and out[key] is not None:
                out[key] = str(out[key])
        clean_articles.append(out)

    return clean_articles, all_flags


# ---------------------------------------------------------------------------
# Research blob sanitizer
# ---------------------------------------------------------------------------

def sanitize_research(text, max_len: int = 1200) -> tuple:
    """Sanitize a web-research string with a larger character budget (default 1200).

    Thin wrapper over sanitize_text. Never raises.
    """
    return sanitize_text(text, max_len=max_len)
