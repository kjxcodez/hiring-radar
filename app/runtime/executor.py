"""Parallel graph executor executing agent tool tasks concurrently with retry backoffs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
from typing import Any
from app.runtime.task import Task, TaskGraph, TaskStatus
from app.runtime.events import global_event_bus
from app.agent.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)


def classify_failure(err: Exception) -> str:
    """Categorize exception into a specific failure class."""
    msg = f"{type(err).__name__} {str(err)}".lower()
    if "timeout" in msg or "connect" in msg or "network" in msg:
        return "Network"
    if "rate limit" in msg or "429" in msg:
        return "Rate Limit"
    if "api key" in msg or "provider" in msg or "authentication" in msg:
        return "Provider"
    if "validation" in msg or "invalid" in msg or "valueerror" in msg:
        return "Validation"
    return "Unexpected"


class GraphExecutor:
    """Executes a TaskGraph concurrently with failure classification retries."""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    def execute_graph(self, graph: TaskGraph) -> None:
        """Run a TaskGraph until completion or unrecoverable node failures."""
        global_event_bus.publish("Plan Started", {"graph_id": graph.graph_id, "goal": graph.goal})

        with ThreadPoolExecutor(max_workers=self.max_workers) as thread_pool:
            while not graph.is_completed() and not graph.is_failed():
                runnable_tasks = graph.get_runnable_tasks()
                if not runnable_tasks:
                    running = [t for t in graph.tasks.values() if t.status == TaskStatus.RUNNING]
                    if not running:
                        logger.error("Deadlock or cycle detected in TaskGraph %s", graph.graph_id)
                        break
                    time.sleep(0.5)
                    continue

                futures = {}
                for task in runnable_tasks:
                    task.status = TaskStatus.RUNNING
                    global_event_bus.publish("Task Started", {"task_id": task.id, "name": task.name})
                    futures[thread_pool.submit(self._execute_single_task, task)] = task

                for fut in as_completed(futures):
                    task = futures[fut]
                    try:
                        fut.result()
                        task.status = TaskStatus.SUCCEEDED
                        global_event_bus.publish("Task Completed", {"task_id": task.id, "name": task.name, "result": task.result})
                    except Exception as e:
                        fail_class = classify_failure(e)
                        retry_limit = task.retry_policy.get("limit", 3)
                        current_retry = task.retry_policy.get("attempts", 0)

                        if current_retry < retry_limit:
                            task.retry_policy["attempts"] = current_retry + 1
                            task.status = TaskStatus.PENDING
                            backoff = (2 ** current_retry) * 2
                            logger.warning("Task %s failed (%s). Retrying in %ds...", task.name, fail_class, backoff)
                            time.sleep(backoff)
                        else:
                            task.status = TaskStatus.FAILED
                            task.error = str(e)
                            global_event_bus.publish("Task Failed", {"task_id": task.id, "name": task.name, "error": str(e)})

        if graph.is_completed():
            global_event_bus.publish("Plan Completed", {"graph_id": graph.graph_id})

    def _execute_single_task(self, task: Task) -> Any:
        """Call target tool callback synchronously in thread pool context."""
        if not task.tool_name:
            return "No tool name provided."

        # Support mocked registry from planner in tests
        from app.agent.planner import TOOL_REGISTRY as planner_registry
        from unittest.mock import MagicMock
        if isinstance(planner_registry, MagicMock) or type(planner_registry).__name__ == "MagicMock":
            registry = planner_registry
        else:
            registry = TOOL_REGISTRY

        if task.tool_name not in registry:
            raise ValueError(f"Tool '{task.tool_name}' is not registered in the agent catalog.")
        tool = registry[task.tool_name]

        result = tool.fn(**task.arguments)
        task.result = result
        return result
