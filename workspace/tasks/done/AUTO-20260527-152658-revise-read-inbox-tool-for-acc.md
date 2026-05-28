---
task_id: AUTO-20260527-152658-revise-read-inbox-tool-for-acc
assigned_agent: heavy_worker
status: done
priority: high
pod: general
task_type: tool_development
created_at: 20260527-152658
---

# Revise `read_inbox` tool for accurate interest flagging and unsubscribe detection

The `read_inbox` tool is incorrectly flagging emails as "interested: true" despite explicit unsubscribe requests or statements of disinterest. This leads to false positives and wasted outreach efforts. The tool's internal logic needs to be refined to accurately interpret email content.

**Specific instance from report:** Email from "Literacy Council" (info@plymouthcantonliteracy.org) regarding "Winding Way Literacy" explicitly stated, "We most definitely have a website. Please remove me from any further emails." but was flagged as interested.

**Deliverables:** Updated `read_inbox` tool logic that correctly identifies and categorizes uninterested emails and unsubscribe requests, preventing false positives. Implement additional checks to prioritize keywords indicating removal or existing services over generic replies.


## Agent Output

## Task Completed: `read_inbox` Tool Revised

### Problem Fixed
The `read_inbox` tool was incorrectly flagging unsubscribe requests as "interested" because it only checked for positive keywords without considering negative context. The specific case from the report — "We **most definitely** have a website. **Please remove me** from any further emails" — was flagged as interested due to the word "definitely."

### Solution Implemented

**1. Priority-Based Detection**
- Unsubscribe/disinterest signals are now checked **FIRST** and take priority over any positive indicators
- Negative context patterns catch positive words used negatively (e.g., "definitely have", "sure we don't")

**2. New Signal Lists**
- `_UNSUBSCRIBE_SIGNALS`: 30+ patterns ("remove me", "unsubscribe", "already have", "not interested", etc.)
- `_NEGATIVE_CONTEXT_PATTERNS`: Regex patterns for flipped meanings
- `_STRONG_INTEREST_PHRASES`: Context-dependent interest indicators ("I'm interested", "call me", "schedule a call")

**3. Removed Weak Triggers**
- Eliminated standalone words like "definitely", "sure", "absolutely", "yes" that caused false positives

**4. Conservative Default**
- Changed from "assume interested if positive word found" to "assume NOT interested unless strong evidence exists"

**5. Enhanced Response**
- Added `interest_reason` and `interest_confidence` fields for transparency

### Files Modified
- `runner/tools/inbox_reader.py` — Complete revision of interest detection logic
- `tests/test_inbox_reader_interest.py` — Comprehensive test suite (25+ test cases)
- `run_inbox_tests.bat` — Quick test runner
