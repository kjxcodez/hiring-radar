"""Progress tracking and reporting for workflow execution."""

from __future__ import annotations

from typing import Any, Callable


class WorkflowProgress:
    """Orchestrates progress reporting for multi-step pipelines.

    Enables CLI, Telegram bot, or Web dashboard UI elements to subscribe to
    real-time progress, steps completed, percent increments, and metrics.
    """

    def __init__(self) -> None:
        self.listeners: list[Callable[[str, dict[str, Any]], None]] = []

    def subscribe(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Register a callback listener that receives progress events."""
        self.listeners.append(callback)

    def start(self, step_name: str, total_steps: int = 1, current_step_index: int = 1) -> None:
        """Report that a step has started, detailing index bounds."""
        self.emit("start", {
            "step_name": step_name,
            "total_steps": total_steps,
            "current_step_index": current_step_index,
        })

    def advance(self, step_name: str, message: str, percent: float | None = None, **kwargs: Any) -> None:
        """Report incremental progress inside an active step."""
        self.emit("advance", {
            "step_name": step_name,
            "message": message,
            "percent": percent,
            **kwargs,
        })

    def fail(self, step_name: str, error: Exception | str) -> None:
        """Report that a step has failed."""
        self.emit("fail", {
            "step_name": step_name,
            "error": str(error),
        })

    def complete(self, step_name: str, result: Any = None) -> None:
        """Report that a step has completed successfully."""
        self.emit("complete", {
            "step_name": step_name,
            "result": result,
        })

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Propagate events to all registered callback listeners."""
        for listener in self.listeners:
            try:
                listener(event_type, data)
            except Exception:  # noqa: S110
                pass  # Do not block execution due to faulty telemetry listeners
