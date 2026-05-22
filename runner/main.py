import concurrent.futures
import logging

from runner.agents.base import AgentBase
from runner.agents.prompts import build_system_prompt
from runner.ledger.budget import is_budget_exceeded
from runner.state.writer import update_agent_state
from runner.tasks.locker import acquire_lock, release_lock
from runner.tasks.reader import read_todo_tasks
from runner.tasks.router import route_task
from runner.tasks.transitions import move_task, write_task_output
from runner.bridge.tony_bridge import scan_and_process as scan_tony_bridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MODELS: dict[str, str] = {
    "manager":                "claude-opus-4-7",
    "heavy_worker":           "claude-sonnet-4-6",
    "debug_worker":           "claude-haiku-4-5",
    "content_worker":         "claude-haiku-4-5",
    "media_worker":           "claude-sonnet-4-6",
    "audio_worker":           "claude-haiku-4-5",
    "guard_worker":           "claude-haiku-4-5",
    "budget_worker":          "claude-haiku-4-5",
    "digital_product_worker": "claude-sonnet-4-6",
    "marketing_worker":       "claude-sonnet-4-6",
}

MAX_CONCURRENT = 4


def run_task(task: dict) -> dict:
    task_id = task["task_id"]
    role_id = route_task(task)

    if not acquire_lock(task_id, role_id):
        log.info("Task %s already locked — skipping", task_id)
        return {"skipped": True, "task_id": task_id}

    try:
        update_agent_state(role_id, "working", task_id)
        move_task(task_id, "todo", "in_progress")

        model = MODELS.get(role_id, "claude-haiku-4-5")
        agent = AgentBase(role_id, model, build_system_prompt(role_id))
        result = agent.run(task)

        write_task_output(task_id, result["output"], "in_progress")
        move_task(task_id, "in_progress", "done")
        update_agent_state(role_id, "idle", "", f"completed {task_id}")
        log.info("%s completed %s ($%.4f)", role_id, task_id, result["cost_usd"])
        return result

    except Exception as exc:
        log.error("%s failed %s: %s", role_id, task_id, exc)
        try:
            move_task(task_id, "in_progress", "failed")
        except Exception:
            pass
        update_agent_state(role_id, "error", task_id, str(exc))
        return {"error": str(exc), "task_id": task_id}

    finally:
        release_lock(task_id)


def run_cycle() -> None:
    if is_budget_exceeded():
        log.warning("Daily budget cap reached — skipping cycle.")
        return

    scan_tony_bridge()
    tasks = read_todo_tasks()
    if not tasks:
        log.info("No tasks in queue.")
        return

    batch = tasks[:MAX_CONCURRENT]
    log.info("Dispatching %d task(s)", len(batch))

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = [executor.submit(run_task, t) for t in batch]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                log.error("Unhandled task error: %s", exc)


if __name__ == "__main__":
    run_cycle()
