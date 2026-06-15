"""Canned LLM completions for the staging twin (CC_LLM_OFFLINE=1).

Staging is a functional tester only — it must make ZERO model calls ($0), while
the pipeline downstream of a verdict still runs for real: write_tony_verdict →
verdicts file → plan_orders → paper brackets → reconcile → EOD ledger. So the
canned market-research completion emits real-shaped write_tony_verdict tool
calls WITH plausible target/stop (target > stop) on every verdict — without
levels, plan_orders' never-open-naked guard skips every buy and the soak's
trade coverage is vacuous.

Shapes mirror exactly the OpenAI SDK attributes AgentBase.run() reads:
response.usage.{prompt,completion}_tokens, choices[0].finish_reason,
choices[0].message.{content,tool_calls}, tc.{id,function.{name,arguments}}.
"""
import json
import os
import re
from types import SimpleNamespace


def llm_offline() -> bool:
    return os.environ.get("CC_LLM_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


# Briefs list tickers as "- **NVDA:** reason ... $120.50" (tony_bridge.py watchlists).
_TICKER_RE = re.compile(r"\*\*([A-Z]{1,5})[:*]")
_PRICE_RE = re.compile(r"\$([0-9]+(?:\.[0-9]+)?)")


def _completion(content: str, tool_calls=None, finish_reason: str = "stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(content=content, tool_calls=tool_calls),
        )],
        usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0),
    )


def _tool_call(idx: int, name: str, args: dict):
    return SimpleNamespace(
        id=f"offline-{idx}",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _verdict_args(symbol: str, price: float) -> dict:
    return {
        "symbol": symbol,
        "tony_score": 70.0,
        "verdict": "reaffirm",
        # plan_orders requires target > stop or the buy is skipped (never-open-naked
        # guard) — reaffirm accepts levels optionally, so always supply them.
        "target": round(price * 1.08, 2),
        "stop": round(price * 0.95, 2),
        "thesis": "[offline] canned staging verdict — no model call, $0",
        "confidence": "medium",
    }


def _canned_verdict_calls(brief: str) -> list:
    calls = []
    seen: set[str] = set()
    for line in brief.splitlines():
        m = _TICKER_RE.search(line)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        pm = _PRICE_RE.search(line)
        price = float(pm.group(1)) if pm else 100.0
        calls.append(_tool_call(len(calls), "write_tony_verdict", _verdict_args(m.group(1), price)))
        if len(calls) == 3:
            break
    if not calls:
        calls.append(_tool_call(0, "write_tony_verdict", _verdict_args("SPY", 100.0)))
    return calls


def offline_completion(role_id: str, kwargs: dict):
    messages = kwargs.get("messages") or []
    if any(isinstance(m, dict) and m.get("role") == "tool" for m in messages):
        return _completion(f"[offline] {role_id}: canned run complete — staging soak, no model call.")
    has_verdict_tool = any(
        (t.get("function") or {}).get("name") == "write_tony_verdict"
        for t in kwargs.get("tools") or []
    )
    if has_verdict_tool:
        brief = next(
            (m.get("content", "") for m in messages
             if isinstance(m, dict) and m.get("role") == "user"), "")
        return _completion("", tool_calls=_canned_verdict_calls(brief), finish_reason="tool_calls")
    return _completion(f"[offline] {role_id}: canned completion — staging soak, no model call.")
