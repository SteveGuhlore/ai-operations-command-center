import anthropic
from runner.ledger.budget import record_spend
from runner.agents.tool_runner import dispatch_tool

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7":   (15.0, 75.0),
    "claude-sonnet-4-6": (3.0,  15.0),
    "claude-haiku-4-5":  (0.8,   4.0),
}


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
        self.client = anthropic.Anthropic()

    def run(self, task: dict) -> dict:
        task_text = f"# Task: {task.get('task_id', 'unknown')}\n\n{task.get('body', '')}"
        messages = [{"role": "user", "content": task_text}]

        total_input = 0
        total_output = 0
        output_text = ""

        kwargs: dict = dict(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=messages,
        )
        if self.tools:
            kwargs["tools"] = self.tools

        while True:
            response = self.client.messages.create(**kwargs)
            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens

            if response.stop_reason == "end_turn":
                output_text = next(
                    (b.text for b in response.content if getattr(b, "type", None) == "text"),
                    "",
                )
                break

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        result = dispatch_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                messages.append({"role": "user", "content": tool_results})
                kwargs["messages"] = messages
                continue

            output_text = next(
                (b.text for b in response.content if getattr(b, "type", None) == "text"),
                str(response.content),
            )
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
