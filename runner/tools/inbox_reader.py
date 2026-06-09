import email
import imaplib
import os
import re
from email.header import decode_header
from dotenv import load_dotenv

# Load environment variables from .env file (needed when tool is imported standalone)
load_dotenv()

# POSITIVE SIGNALS - words/phrases indicating interest
_INTEREST_SIGNALS = [
    "interested", "tell me more", "sounds good", "how much",
    "price", "pricing", "more info", "let's talk", "let's do",
    "when can", "love to", "great idea", "absolutely interested",
    "send me", "send examples", "see examples", "keep me posted",
    "reach out", "follow up", "move forward", "next steps",
    "would like to learn", "sounds interesting", "worth discussing",
    "open to", "looking for", "need help", "could use",
]

# STRONG INTEREST PHRASES - require specific context
_STRONG_INTEREST_PHRASES = [
    "i'm interested", "i am interested", "we are interested", "we're interested",
    "yes please", "yes, please", "yes i am", "yes i'm",
    "call me", "email me back", "reply back", "get back to me",
    "schedule a call", "set up a call", "book a call",
    "how does it work", "tell me more about", "give me more info",
    "what are the next steps", "where do we start", "ready to start",
]

# NEGATIVE/UNSUBSCRIBE SIGNALS - phrases indicating disinterest or removal requests
_UNSUBSCRIBE_SIGNALS = [
    # Direct unsubscribe/removal requests
    "unsubscribe", "remove me", "take me off", "take us off",
    "delete my email", "stop emailing", "stop sending",
    "no longer interested", "not interested",
    "do not contact", "do not email", "do not send",
    "opt out", "opt-out", "mailing list",
    # Rejection phrases. NOTE: "we have a" / "already have" / "currently use" moved to
    # _NEGATIVE_CONTEXT_PATTERNS with an explicit website/builder object — the bare substrings
    # rejected hot replies like "sounds good, we have a budget for this — how much?".
    "not for us", "not a fit", "not interested",
    "no thank", "no thanks", "no need", "not now",
    "happy with", "satisfied with", "don't need", "do not need",
    "won't need", "will not need", "not looking",
    # Firm negatives
    "please don't", "please do not", "never contact", "never email",
    "wrong person", "wrong email", "not my job", "not the right",
]

_SITE_OBJECT = r"(?:web\s?site|website|site|web\s?page|homepage|web\s+(?:guy|person|team|company))"

# NEGATIVE CONTEXT PHRASES - words that flip meaning when combined
_NEGATIVE_CONTEXT_PATTERNS = [
    r"definitely\s+(?:not|don't|do not|won't|will not)",
    rf"(?:we|i)\s+(?:already|definitely)\s+have\s+a\s+(?:new\s+)?{_SITE_OBJECT}",
    rf"already\s+have\s+a\s+(?:new\s+)?{_SITE_OBJECT}",
    r"(?:we|i)\s+(?:already|currently)\s+use\s+(?:wix|squarespace|godaddy|weebly|wordpress|shopify|another)",
    r"\bnot\s+(?:interested|looking|available)",
    r"(?:please|kindly)\s+(?:remove|unsubscribe|stop|delete)",
    r"do\s+not\s+(?:contact|email|send|need)",
    # "Never call me again" must read as opt-out, not as the strong-interest phrase "call me".
    r"(?:never|don'?t|do\s+not|stop)\s+(?:call|email|contact|text)",
    r"(?:take|remove)\s+(?:us|me)\s+(?:off|from)",
    r"wrong\s+(?:person|department|email|address)",
]


def _decode_header_value(raw) -> str:
    parts = decode_header(raw or "")
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    # Respect the sender's declared charset — Outlook et al send windows-1252 smart quotes
    # that mojibake under a blind utf-8 decode, breaking apostrophe phrases ("i'm interested").
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def _strip_html(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _body_text(msg) -> str:
    plain, html = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and not plain:
                plain = _decode_part(part)
            elif ctype == "text/html" and not html:
                html = _decode_part(part)
    else:
        if msg.get_content_type() == "text/html":
            html = _decode_part(msg)
        else:
            plain = _decode_part(msg)
    # HTML-only replies (Outlook mobile) used to analyze an empty body; strip tags instead.
    return (plain or _strip_html(html))[:2000]


_QUOTE_MARKERS = re.compile(
    r"^\s*on .{0,120}wrote:\s*$|^-{2,}\s*original message\s*-{2,}|^from:\s.+$",
    re.IGNORECASE | re.MULTILINE)


def _strip_quoted(body: str) -> str:
    """Drop quoted reply content before analysis. Our own pitch contains 'unsubscribe'/'STOP'
    (CAN-SPAM footer), so analyzing the quote classified every interested reply that quoted the
    original as an opt-out — the tool's purpose inverted."""
    m = _QUOTE_MARKERS.search(body)
    if m:
        body = body[:m.start()]
    return "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith(">"))


# Standalone = high-precision: safe to classify as auto-reply on this phrase alone.
_AUTO_REPLY_SIGNALS = [
    "out of office", "out-of-office", "auto-reply", "auto reply",
    "automatic reply", "autoreply", "i am away", "i'm away",
    "i am out of", "i'm out of", "currently out of",
    "on vacation", "on holiday", "annual leave", "maternity leave",
    "this is an automated", "do not reply", "do-not-reply",
    "no longer with", "no longer at this", "no longer employed",
    "undeliverable", "delivery status notification", "mail delivery failed",
    "address not found", "user unknown", "mailbox full",
]

# Weak phrases that real humans also write ("I received your email, yes I'm interested!") —
# they only count as auto-reply alongside an auto-submitted header or a second weak phrase.
_AUTO_REPLY_WEAK = [
    "received your email", "received your message",
    "thank you for contacting", "we have received your",
    "will be back", "will return", "back in the office",
]


def _is_auto_reply(subject: str, body: str, headers: dict | None = None) -> bool:
    text = (subject + " " + body).lower()
    header_auto = False
    if headers:
        if headers.get("auto-submitted", "").lower().startswith("auto"):
            header_auto = True
        if headers.get("x-auto-response-suppress"):
            header_auto = True
        if headers.get("precedence", "").lower() in ("auto_reply", "bulk", "junk"):
            header_auto = True
    if header_auto:
        return True
    if any(sig in text for sig in _AUTO_REPLY_SIGNALS):
        return True
    weak_hits = sum(1 for sig in _AUTO_REPLY_WEAK if sig in text)
    return weak_hits >= 2


def _has_unsubscribe_signals(subject: str, body: str) -> tuple[bool, str]:
    """
    Check for unsubscribe/disinterest signals. Returns (has_signal, reason).
    """
    text = (subject + " " + body).lower()
    
    # Check for negative context patterns first (strong indicators)
    for pattern in _NEGATIVE_CONTEXT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"Negative context pattern matched: {pattern}"
    
    # Check for explicit unsubscribe/removal signals
    for signal in _UNSUBSCRIBE_SIGNALS:
        if signal in text:
            return True, f"Unsubscribe signal: '{signal}'"
    
    return False, ""


def _has_strong_interest(subject: str, body: str) -> tuple[bool, str]:
    """
    Check for strong interest indicators that override simple word matches.
    Returns (has_interest, reason).
    """
    text = (subject + " " + body).lower()
    
    # Check for strong interest phrases — but a negation right before flips the meaning
    # ("Never call me again" must not match the strong phrase "call me").
    negations = ("never ", "don't ", "do not ", "won't ", "stop ", "not ")
    for phrase in _STRONG_INTEREST_PHRASES:
        pos = text.find(phrase)
        if pos >= 0:
            lead = text[max(0, pos - 30):pos]
            if not any(neg in lead for neg in negations):
                return True, f"Strong interest phrase: '{phrase}'"
    
    # Check for positive signals that are NOT negated
    for signal in _INTEREST_SIGNALS:
        if signal in text:
            # Verify it's not in a negative context
            signal_pos = text.find(signal)
            # Look at surrounding context (50 chars before)
            context_start = max(0, signal_pos - 50)
            context = text[context_start:signal_pos + len(signal) + 20]
            
            # Check if preceded by negation words
            negation_words = ["not ", "no ", "n't ", "never ", "don't ", "doesn't ", "won't ", "wouldn't "]
            if not any(neg in context.lower() for neg in negation_words):
                return True, f"Positive signal: '{signal}'"
    
    return False, ""


def _is_interested(subject: str, body: str, headers: dict | None = None) -> dict:
    """
    Determine if an email indicates genuine buying interest.
    Returns a dict with detailed analysis.
    """
    # Analyze only the prospect's OWN words — the quoted pitch below their reply contains our
    # CAN-SPAM footer ("unsubscribe"/"STOP"), which used to mark every quoting reply as opt-out.
    body = _strip_quoted(body)
    # Auto-replies are never interested
    if _is_auto_reply(subject, body, headers):
        return {
            "interested": False,
            "confidence": "high",
            "reason": "Auto-reply detected",
        }
    
    # Check for unsubscribe/disinterest signals FIRST (takes priority)
    has_unsub, unsub_reason = _has_unsubscribe_signals(subject, body)
    if has_unsub:
        return {
            "interested": False,
            "confidence": "high",
            "reason": unsub_reason,
        }
    
    # Check for strong interest indicators
    has_interest, interest_reason = _has_strong_interest(subject, body)
    if has_interest:
        return {
            "interested": True,
            "confidence": "medium",
            "reason": interest_reason,
        }
    
    # Default: not interested (conservative approach)
    return {
        "interested": False,
        "confidence": "high",
        "reason": "No clear interest indicators found",
    }


def read_inbox(max_messages: int = 30, unread_only: bool = False) -> dict:
    host     = os.environ.get("IMAP_HOST", "imap.gmail.com")
    port     = int(os.environ.get("IMAP_PORT", "993"))
    user     = os.environ.get("IMAP_USER", "")
    password = os.environ.get("IMAP_PASSWORD", "")

    if not user or not password:
        return {
            "error": "IMAP_USER and IMAP_PASSWORD not set in .env — cannot read inbox",
            "messages": [],
            "interested_count": 0,
        }

    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(user, password)
        mail.select("INBOX")

        criteria = "(UNSEEN)" if unread_only else "ALL"
        status, data = mail.search(None, criteria)
        if status != "OK":
            return {"error": "IMAP search failed", "messages": [], "interested_count": 0}

        ids = data[0].split()
        recent_ids = ids[-max_messages:]

        messages = []
        interested_messages = []
        
        for uid in reversed(recent_ids):
            status, msg_data = mail.fetch(uid, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            sender  = _decode_header_value(msg.get("From", ""))
            subject = _decode_header_value(msg.get("Subject", ""))
            date    = msg.get("Date", "")
            body    = _body_text(msg)
            headers = {
                "auto-submitted":            msg.get("Auto-Submitted", ""),
                "x-auto-response-suppress":  msg.get("X-Auto-Response-Suppress", ""),
                "precedence":                msg.get("Precedence", ""),
            }
            
            auto_reply = _is_auto_reply(subject, body, headers)
            interest_analysis = _is_interested(subject, body, headers)
            interested = interest_analysis["interested"]

            message_data = {
                "uid":              uid.decode(),
                "from":             sender,
                "subject":          subject,
                "date":             date,
                "body":             body[:500],
                "auto_reply":       auto_reply,
                "interested":       interested,
                "interest_reason":  interest_analysis.get("reason", ""),
                "interest_confidence": interest_analysis.get("confidence", ""),
            }
            
            messages.append(message_data)
            
            if interested:
                interested_messages.append(message_data)

        mail.logout()

        return {
            "messages":         messages,
            "total":            len(messages),
            "interested_count": len(interested_messages),
            "interested":       interested_messages,
        }

    except imaplib.IMAP4.error as exc:
        return {"error": f"IMAP auth/connection error: {exc}", "messages": [], "interested_count": 0}
    except Exception as exc:
        return {"error": str(exc), "messages": [], "interested_count": 0}


TOOL_SPEC = {
    "name": "read_inbox",
    "description": (
        "Read recent emails from the outreach inbox via IMAP. "
        "Returns all messages and flags any that show genuine buying interest (positive reply to a pitch). "
        "Uses conservative detection: prioritizes unsubscribe/disinterest signals over generic positive words. "
        "Use this at the start of every outreach run to check for replies before sending new pitches."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "max_messages": {
                "type": "integer",
                "description": "How many recent messages to read (default 30)",
                "default": 30,
            },
            "unread_only": {
                "type": "boolean",
                "description": "If true, only fetch unread messages",
                "default": False,
            },
        },
        "required": [],
    },
}
