"""Global kill-switch for paid LLM/AI calls.

Set CC_LLM_DISABLED=1 (or true/yes/on) to make every agent, tool, and script skip its
LLM/AI call cleanly — no client construction, no spend, no error-spam — while the upstream
provider APIs are turned off. One source of truth so a single env flag guarantees $0 across
base.py (agents), the image/audio tools, and the nightly improvement loop.
"""

import os

_TRUTHY = {"1", "true", "yes", "on"}


def llm_disabled() -> bool:
    """True when CC_LLM_DISABLED is set to a truthy value (1/true/yes/on)."""
    return os.environ.get("CC_LLM_DISABLED", "").strip().lower() in _TRUTHY
