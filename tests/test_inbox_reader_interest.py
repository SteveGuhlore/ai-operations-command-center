"""
Test suite for inbox_reader interest detection.
Tests the specific case from the report and various edge cases.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'runner', 'tools'))

from inbox_reader import (
    _is_interested,
    _has_unsubscribe_signals,
    _has_strong_interest,
    _is_auto_reply,
)


def test_unsubscribe_detection():
    """Test that unsubscribe requests are correctly identified."""
    
    # The specific case from the report
    subject = "Re: Website help for Winding Way Literacy"
    body = """Hi,

We most definitely have a website. Please remove me from any further emails.

Thanks,
Jane Doe"""
    
    result = _is_interested(subject, body, {})
    assert result["interested"] == False, f"Should NOT flag as interested. Got: {result}"
    assert "remove" in result["reason"].lower() or "unsubscribe" in result["reason"].lower(), f"Should mention removal reason. Got: {result}"
    print("✓ PASS: Reported case correctly flagged as NOT interested")
    
    # Test other unsubscribe variations
    test_cases = [
        ("Remove me", "Please remove me from your mailing list", False),
        ("Unsubscribe", "Please unsubscribe me from future emails", False),
        ("Stop emailing", "Stop sending me emails", False),
        ("Not interested", "We are not interested, thanks", False),
        ("Already have", "We already have a website, no thanks", False),
        ("Do not contact", "Please do not contact us again", False),
        ("Take us off", "Take us off your list please", False),
        ("No longer", "I am no longer with the company", False),
        ("Wrong person", "You have the wrong person/email", False),
        ("Happy with current", "We are happy with our current provider", False),
    ]
    
    for subject, body, expected in test_cases:
        result = _is_interested(subject, body, {})
        assert result["interested"] == expected, f"Failed for '{subject}': expected {expected}, got {result}"
        print(f"✓ PASS: '{subject}' correctly flagged as {expected}")


def test_positive_interest():
    """Test that genuine interest is correctly identified."""
    
    test_cases = [
        ("Interested", "I am interested in your services", True),
        ("Tell me more", "Can you tell me more about pricing?", True),
        ("Call me", "Please call me to discuss", True),
        ("Schedule call", "Let's schedule a call", True),
        ("Send info", "Please send me more information", True),
        ("Love to", "I would love to learn more", True),
        ("Next steps", "What are the next steps?", True),
        ("How much", "How much does this cost?", True),
    ]
    
    for subject, body, expected in test_cases:
        result = _is_interested(subject, body, {})
        assert result["interested"] == expected, f"Failed for '{subject}': expected {expected}, got {result}"
        print(f"✓ PASS: '{subject}' correctly flagged as {expected}")


def test_negative_context():
    """Test that positive words in negative contexts are handled."""
    
    # "definitely" alone was triggering interest before
    test_cases = [
        ("We definitely have", "We definitely have a website already", False),
        ("Most definitely", "We most definitely have this covered", False),
        ("Definitely not", "We are definitely not interested", False),
        ("Sure", "I'm sure we don't need this", False),
        ("Absolutely not", "Absolutely not interested, thanks", False),
        ("Yes but no", "Yes, but we don't need it", False),  # Edge case
    ]
    
    for subject, body, expected in test_cases:
        result = _is_interested(subject, body, {})
        assert result["interested"] == expected, f"Failed for '{subject}': expected {expected}, got {result}"
        print(f"✓ PASS: '{subject}' correctly flagged as {expected}")


def test_auto_reply_detection():
    """Test auto-reply detection."""
    
    auto_replies = [
        ("Out of office", "I am currently out of the office"),
        ("Auto-reply", "This is an automatic reply"),
        ("Vacation", "I am on vacation until next week"),
        ("Away", "I'm away from my desk"),
    ]
    
    for subject, body in auto_replies:
        result = _is_interested(subject, body, {})
        assert result["interested"] == False, f"Auto-reply '{subject}' should not be interested"
        assert "auto" in result["reason"].lower(), f"Should mention auto-reply reason. Got: {result}"
        print(f"✓ PASS: Auto-reply '{subject}' correctly flagged")


def test_ambiguous_cases():
    """Test ambiguous cases that should default to not interested (conservative)."""
    
    ambiguous = [
        ("Thanks", "Thanks for reaching out"),  # Polite but no clear intent
        ("Info", "I received your email"),  # Acknowledgment only
        ("Question", "What is this about?"),  # Question but no commitment
    ]
    
    for subject, body in ambiguous:
        result = _is_interested(subject, body, {})
        # Conservative: default to not interested if unclear
        print(f"  INFO: '{subject}' result: {result}")


def test_specific_report_case():
    """Reproduce the exact scenario from the bug report."""
    
    # From Literacy Council email
    report_subject = "Re: Website help for Winding Way Literacy"
    report_body = """We most definitely have a website. Please remove me from any further emails.

Thanks,
Literacy Council"""
    
    result = _is_interested(report_subject, report_body, {})
    
    print(f"\n=== REPORTED CASE TEST ===")
    print(f"Subject: {report_subject}")
    print(f"Body preview: {report_body[:100]}...")
    print(f"Result: interested={result['interested']}")
    print(f"Reason: {result['reason']}")
    print(f"Confidence: {result['confidence']}")
    
    assert result["interested"] == False, "CRITICAL: The reported case MUST be flagged as NOT interested"
    print("✓ PASS: Reported case correctly handled!")


if __name__ == "__main__":
    print("Running inbox_reader interest detection tests...\n")
    
    test_specific_report_case()
    print()
    
    test_unsubscribe_detection()
    print()
    
    test_positive_interest()
    print()
    
    test_negative_context()
    print()
    
    test_auto_reply_detection()
    print()
    
    test_ambiguous_cases()
    print()
    
    print("\n" + "="*50)
    print("ALL TESTS PASSED!")
    print("="*50)
