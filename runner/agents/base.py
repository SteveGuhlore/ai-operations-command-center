import json
import os

import openai

from runner.ledger.budget import record_spend
from runner.agents.tool_runner import dispatch_tool

# (input_$/MTok, output_$/MTok) — OpenRouter prices
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "anthropic/claude-sonnet-4-6": (3.0,  15.0),
    "anthropic/claude-haiku-4-5":  (0.8,   4.0),
    "moonshotai/kimi-k2.5":        (0.60,  3.0),
    "minimax/minimax-m2.5":        (0.15,  1.15),
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

        max_tokens = 8192 if self.role_id in (
            "digital_product_worker", "content_worker", "heavy_worker"
        ) else 4096

        oai_tools = _to_openai_tools(self.tools) if self.tools else None

        kwargs: dict = dict(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
        )
        if oai_tools:
            kwargs["tools"] = oai_tools

        while True:
            response = self.client.chat.completions.create(**kwargs)
            usage = response.usage
            if usage:
                total_input += usage.prompt_tokens
                total_output += usage.completion_tokens

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
                    tool_input = json.loads(tc.function.arguments)
                    result = dispatch_tool(tc.function.name, tool_input)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })

                kwargs["messages"] = messages
                continue

            output_text = msg.content or ""
            break

        cost = calculate_cost(self.model, total_input, total_output)
        record_spend(self.role_id, cost)

        return {
            "role_id": self.role_id,
            "task_id": task.get("task_id"),
            "output": output_text,
            "cost_usd": cost,
            "input_tokens": total_input,
            "output_tokens": total_output,
        }
