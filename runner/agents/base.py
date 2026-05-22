import anthropic
from runner.ledger.budget import record_spend

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7":   (15.0, 75.0),
    "claude-sonnet-4-6": (3.0,  15.0),
    "claude-haiku-4-5":  (0.8,   4.0),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = MODEL_PRICING.get(model, (3.0, 15.0))
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class AgentBase:
    def __init__(self, role_id: str, model: str, system_prompt: str):
        self.role_id = role_id
        self.model = model
        self.system_prompt = system_prompt
        self.client = anthropic.Anthropic()

    def run(self, task: dict) -> dict:
        task_text = f"# Task: {task.get('task_id', 'unknown')}\n\n{task.get('body', '')}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": task_text}],
        )

        output_text = response.content[0].text
        cost = calculate_cost(self.model, response.usage.input_tokens, response.usage.output_tokens)
        record_spend(self.role_id, cost)

        return {
            "role_id": self.role_id,
            "task_id": task.get("task_id"),
            "output": output_text,
            "cost_usd": cost,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
