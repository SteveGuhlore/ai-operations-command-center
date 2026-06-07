import json
import os

import openai

from runner.ledger.budget import record_spend
from runner.agents.tool_runner import dispatch_tool

# Vertex AI: lazy-imported only when VERTEX_PROJECT is set so the rest of the
# system stays runnable without google-auth installed.
_vertex_creds = None
_vertex_request = None


def _vertex_token() -> str:
    global _vertex_creds, _vertex_request
    if _vertex_creds is None:
        import google.auth
        import google.auth.transport.requests
        _vertex_creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        _vertex_request = google.auth.transport.requests.Request()
    if not _vertex_creds.valid:
        _vertex_creds.refresh(_vertex_request)
    return _vertex_creds.token

# (input_$/MTok, output_$/MTok)
MODEL_PRICING: dict[str, tuple[float, float]] = {
"moonshotai/kimi-k2.5":         (0.60,   3.0),
    "minimax/minimax-m2.5":         (0.15,   1.15),
    "google/gemini-flash-1.5":      (0.075,  0.30),  # via OpenRouter
    "gemini-1.5-flash":             (0.075,  0.30),  # Google direct
    "gemini-2.0-flash":             (0.10,   0.40),  # Google direct
    "gemini-2.5-flash":             (0.30,   2.50),  # Google direct — primary worker model
    "gemini-2.5-flash-lite":        (0.10,   0.40),  # Google direct
    "gemini-2.5-pro":               (1.25,  10.00),  # Google direct — Atlas + Tony Stocks
    "claude-opus-4-8":              (15.0,  75.0),   # Claude builds (see 2026-05-29 spec)
    "claude-opus-4-7":              (15.0,  75.0),
    "claude-sonnet-4-6":            (3.0,   15.0),
    "claude-haiku-4-5":             (0.80,   4.0),
}


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool spec (input_schema) to OpenAI function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = MODEL_PRICING.get(model, (3.0, 15.0))
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class AgentBase:
    def __init__(
        self,
        role_id: str,
        model: str,
        system_prompt: str,
        tools: list[dict] | None = None,
    ):
        self.role_id = role_id
        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools or []
        # Routing precedence:
        #   1. VERTEX_PROJECT set + gemini-* model  -> Vertex AI (uses $300 GCP credit)
        #   2. GOOGLE_AI_API_KEY set + slash-free   -> AI Studio Gemini API
        #   3. everything else                      -> OpenRouter
        # Accept both the CC's own names (VERTEX_*) and the google-genai SDK names
        # (GOOGLE_CLOUD_*) the VM deployment sets, so one .env works everywhere.
        vertex_project = os.environ.get("VERTEX_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        google_key = os.environ.get("GOOGLE_AI_API_KEY")
        self._use_vertex = False
        if vertex_project and model.startswith("gemini-"):
            location = (os.environ.get("VERTEX_LOCATION")
                        or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))
            self._use_vertex = True
            self.model = f"google/{model}"
            self.client = openai.OpenAI(
                base_url=(
                    f"https://{location}-aiplatform.googleapis.com/v1beta1/"
                    f"projects/{vertex_project}/locations/{location}/endpoints/openapi"
                ),
                api_key=_vertex_token(),
            )
        elif "/" not in model and google_key:
            self.client = openai.OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=google_key,
            )
        else:
            self.client = openai.OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY"),
            )

    def run(self, task: dict) -> dict:
        task_text = f"# Task: {task.get('task_id', 'unknown')}\n\n{task.get('body', '')}"
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task_text},
        ]

        total_input = 0
        total_output = 0
        output_text = ""

        if self.role_id == "builder":
            # Clay runs gemini-2.5-pro (a thinking model) AND must emit a full HTML page.
            # At 4096 the model spends the budget reasoning and hits finish_reason=length
            # before any tool call -> empty output, no page. Give it room to think + write.
            max_tokens = 32768
        elif self.role_id == "market_research_worker":
            # Tony runs gemini-2.5-pro (thinking) over a heavy brief (7KB EOD report + history)
            # and must still emit analysis + tool calls. At 4096 he hit finish_reason=length and
            # returned "(no tool calls made this run)" — same trap as Clay. Give him room.
            max_tokens = 16384
        elif self.role_id in (
            "digital_product_worker", "content_worker", "heavy_worker", "outreach_worker"
        ):
            max_tokens = 8192
        else:
            max_tokens = 4096

        oai_tools = _to_openai_tools(self.tools) if self.tools else None

        kwargs: dict = dict(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
        )
        if oai_tools:
            kwargs["tools"] = oai_tools

        max_steps = 25 if self.role_id == "outreach_worker" else 50
        step = 0
        tool_calls_total = 0
        tool_calls_errored = 0
        while step < max_steps:
            if self._use_vertex:
                self.client.api_key = _vertex_token()
            response = self.client.chat.completions.create(**kwargs)
            usage = response.usage
            if usage:
                total_input += usage.prompt_tokens or 0
                total_output += usage.completion_tokens or 0

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            msg = choice.message

            if finish_reason == "tool_calls" and msg.tool_calls:
                # Append assistant message with tool_calls serialised as plain dict
                assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
                messages.append(assistant_entry)

                for tc in msg.tool_calls:
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except (json.JSONDecodeError, TypeError) as exc:
                        # The model emitted malformed JSON for this tool call's
                        # arguments. Don't crash the whole task (this killed PoC
                        # builds) — feed the parse error back so it resends valid
                        # JSON on the next turn.
                        tool_calls_total += 1
                        tool_calls_errored += 1
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({
                                "error": f"Invalid JSON in tool arguments: {exc}. "
                                         f"Resend this tool call with valid JSON."
                            }),
                        })
                        continue
                    result = dispatch_tool(tc.function.name, tool_input)
                    tool_calls_total += 1
                    if isinstance(result, dict) and result.get("error"):
                        tool_calls_errored += 1
                    try:
                        content = json.dumps(result, default=str)
                    except (TypeError, ValueError):
                        content = str(result)
                    limit = 20000 if tc.function.name == "file_editor" else 4000
                    if len(content) > limit:
                        content = content[:limit] + "\n...[truncated]"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": content,
                    })

                kwargs["messages"] = messages
                step += 1
                continue

            output_text = msg.content or ""

            # If outreach_worker found prospects but never wrote to CRM, force it
            if self.role_id == "outreach_worker":
                called = {
                    tc["function"]["name"]
                    for m in messages if isinstance(m, dict) and m.get("role") == "assistant"
                    for tc in (m.get("tool_calls") or [])
                }
                wrote_crm = any(
                    tc["function"]["name"] == "file_editor" and
                    ('"write"' in tc["function"].get("arguments", "") or
                     '"append"' in tc["function"].get("arguments", ""))
                    for m in messages if isinstance(m, dict) and m.get("role") == "assistant"
                    for tc in (m.get("tool_calls") or [])
                )
                if "find_prospects" in called and not wrote_crm:
                    messages.append({"role": "assistant", "content": output_text})
                    messages.append({
                        "role": "user",
                        "content": (
                            "You found prospects but have NOT called file_editor to update "
                            "vault/outreach/crm.md. Use action=append to add the new rows now. Do it immediately."
                        )
                    })
                    kwargs["messages"] = messages
                    output_text = ""
                    step += 1
                    continue

            break

        all_tools_errored = tool_calls_total > 0 and tool_calls_errored == tool_calls_total

        # Gemini often returns empty content after tool calls — build summary from actual data
        if not output_text.strip():
            tool_names = [
                tc["function"]["name"]
                for m in messages if isinstance(m, dict) and m.get("role") == "assistant"
                for tc in (m.get("tool_calls") or [])
            ]
            if tool_names:
                tail = "ALL_TOOLS_ERRORED" if all_tools_errored else "(agent returned no text summary — see the files it changed)"
                output_text = f"Run completed via tool calls: {', '.join(dict.fromkeys(tool_names))}. {tail}"
            else:
                output_text = "(no tool calls made this run)"
        elif all_tools_errored and "ALL_TOOLS_ERRORED" not in output_text:
            output_text = output_text.rstrip() + "\n\nALL_TOOLS_ERRORED"

        cost = calculate_cost(self.model, total_input, total_output)
        record_spend(self.role_id, cost, pod=task.get("pod"))

        return {
            "role_id": self.role_id,
            "task_id": task.get("task_id"),
            "output": output_text,
            "cost_usd": cost,
            "input_tokens": total_input,
            "output_tokens": total_output,
        }
