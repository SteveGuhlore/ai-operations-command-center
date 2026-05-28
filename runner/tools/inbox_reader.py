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
    # Rejection phrases
    "not for us", "not a fit", "not interested",
    "no thank", "no thanks", "no need", "not now",
    "already have", "we have a", "already use", "currently use",
    "happy with", "satisfied with", "don't need", "do not need",
    "won't need", "will not need", "not looking",
    # Firm negatives
    "please don't", "please do not", "never contact", "never email",
    "wrong person", "wrong email", "not my job", "not the right",
]

# NEGATIVE CONTEXT PHRASES - words that flip meaning when combined
_NEGATIVE_CONTEXT_PATTERNS = [
    r"definitely\s+(?:have|not|don't|do not|won't|will not)",
    r"most\s+definitely\s+(?:have|not|don't|do not)",
    r"we\s+(?:already|definitely)\s+have\s+a",
    r"we\s+(?:already|currently)\s+use",
    r"not?\s+(?:interested|looking|available|interested)",
    r"(?:please|kindly)\s+(?:remove|unsubscribe|stop|delete)",
    r"do\s+not\s+(?:contact|email|send|need)",
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


def _body_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="replace")[:2000]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(errors="replace")[:2000]
    return ""


_AUTO_REPLY_SIGNALS = [
    "out of office", "out-of-office", "auto-reply", "auto reply",
    "automatic reply", "autoreply", "i am away", "i'm away",
    "i am out of", "i'm out of", "currently out of",
    "on vacation", "on holiday", "annual leave", "maternity leave",
    "will be back", "will return", "back in the office",
    "received your email", "received your message",
    "this is an automated", "do not reply", "do-not-reply",
    "no longer with", "no longer at this", "no longer employed",
    "undeliverable", "delivery status notification", "mail delivery failed",
    "address not found", "user unknown", "mailbox full",
    "thank you for contacting", "we have received your",
]


def _is_auto_reply(subject: str, body: str, headers: dict | None = None) -> bool:
    text = (subject + " " + body).lower()
    if any(sig in text for sig in _AUTO_REPLY_SIGNALS):
        return True
    if headers:
        if headers.get("auto-submitted", "").lower().startswith("auto"):
            return True
        if headers.get("x-auto-response-suppress"):
            return True
        if headers.get("precedence", "").lower() in ("auto_reply", "bulk", "junk"):
            return True
    return False


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
    
    # Check for strong interest phrases
    for phrase in _STRONG_INTEREST_PHRASES:
        if phrase in text:
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
