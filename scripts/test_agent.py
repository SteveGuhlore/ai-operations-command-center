"""
Single-agent test harness. Run one agent against one task file.

Usage:
    python scripts/test_agent.py --role debug_worker --task workspace/tasks/todo/SAMPLE-001-debug-worker-environment-check.md
    python scripts/test_agent.py --role content_worker --task workspace/tasks/todo/POD-ETSY-001-product-listing.md
    python scripts/test_agent.py --role digital_product_worker --task workspace/tasks/todo/POD-DIG-001-guide-creation.md
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from runner.agents.base import AgentBase
from runner.agents.prompts import build_system_prompt
from runner.tasks.reader import parse_task_file
from runner.main import MODELS, ROLE_TOOLS


def main():
    parser = argparse.ArgumentParser(description="Run one agent against one task file.")
    parser.add_argument("--role", required=True, help="Agent role ID (e.g. debug_worker, content_worker)")
    parser.add_argument("--task", required=True, help="Path to task .md file")
    parser.add_argument("--dry-run", action="store_true", help="Print system prompt only, no API call")
    args = parser.parse_args()

    task_path = Path(args.task)
    if not task_path.exists():
        print(f"ERROR: Task file not found: {task_path}")
        sys.exit(1)

    task = parse_task_file(task_path)
    model = MODELS.get(args.role, "claude-haiku-4-5")
    system_prompt = build_system_prompt(args.role)

    print(f"\n{'='*60}")
    print(f"  Agent: {args.role}  |  Model: {model}")
    print(f"  Task:  {task.get('task_id', task_path.name)}")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("--- SYSTEM PROMPT ---")
        print(system_prompt[:2000])
        print("--- TASK BODY ---")
        print(task.get("body", "")[:1000])
        return

    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to .env in the project root.")
        sys.exit(1)

    tools = ROLE_TOOLS.get(args.role, [])
    print(f"  Tools: {[t['name'] for t in tools] or 'none'}\n")
    print("Calling Claude API...\n")
    agent = AgentBase(args.role, model, system_prompt, tools=tools)
    result = agent.run(task)

    # Save output to workspace/outputs/
    out_dir = Path(__file__).parent.parent / "workspace" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    task_id = task.get("task_id", task_path.stem)
    out_file = out_dir / f"{task_id}-output.md"
    out_file.write_text(result["output"], encoding="utf-8")

    print("--- OUTPUT ---")
    sys.stdout.buffer.write((result["output"][:3000] + ("\n...(truncated — see full output in workspace/outputs/)" if len(result["output"]) > 3000 else "") + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()
    print(f"\n--- COST: ${result['cost_usd']:.4f} | in: {result['input_tokens']} | out: {result['output_tokens']} ---")
    print(f"--- SAVED: {out_file} ---")


if __name__ == "__main__":
    main()
