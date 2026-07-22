"""Sequential executor for workflows and cancellation manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from app.workflows.events import (
    StepFailed,
    StepFinished,
    StepStarted,
)

if TYPE_CHECKING:
    from app.workflows.context import WorkflowContext
    from app.workflows.workflow import Workflow

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Executes a defined pipeline of WorkflowSteps sequentially.

    Monitors cancellation flags between steps and notifies telemetry event listeners
    registered on the execution lifecycle.
    """

    def __init__(self) -> None:
        self.event_listeners: list[Callable[[Any], None]] = []

    def register_listener(self, listener: Callable[[Any], None]) -> None:
        """Register a callback that receives lifecycle StepEvents."""
        self.event_listeners.append(listener)

    def _emit(self, event: Any, context: WorkflowContext) -> None:
        """Dispatch a step-level execution event to all registered listeners."""
        for listener in self.event_listeners:
            try:
                listener(event)
            except Exception:  # noqa: S110
                pass
        if context.event_dispatcher:
            try:
                context.event_dispatcher(event)
            except Exception:  # noqa: S110
                pass

    def execute(self, workflow: Workflow, context: WorkflowContext) -> Any:
        """Sequential workflow steps executor."""
        logger.info(
            "workflow/executor/%s: starting execution of workflow '%s'",
            context.execution_id,
            workflow.name,
        )

        total_steps = len(workflow.steps)
        last_result = None

        for idx, step in enumerate(workflow.steps, 1):
            # 1. Check for cancellation before executing step
            if context.cancelled:
                logger.warning(
                    "workflow/executor/%s: execution cancelled before step '%s'",
                    context.execution_id,
                    step.name,
                )
                raise RuntimeError("Workflow execution was cancelled.")

            # 2. Emit StepStarted event
            logger.info(
                "workflow/executor/%s: executing step %d/%d (%s)",
                context.execution_id,
                idx,
                total_steps,
                step.name,
            )
            self._emit(
                StepStarted(
                    workflow_name=workflow.name,
                    execution_id=context.execution_id,
                    step_name=step.name,
                ),
                context
            )
            context.progress.start(step.name, total_steps, idx)

            try:
                # 3. Execute step logic
                last_result = step.execute(context)

                # 4. Emit StepFinished event
                self._emit(
                    StepFinished(
                        workflow_name=workflow.name,
                        execution_id=context.execution_id,
                        step_name=step.name,
                        result=last_result,
                    ),
                    context
                )
                context.progress.complete(step.name, result=last_result)

            except Exception as exc:
                logger.error(
                    "workflow/executor/%s: step '%s' failed — %s",
                    context.execution_id,
                    step.name,
                    exc,
                )
                # Emit StepFailed event
                self._emit(
                    StepFailed(
                        workflow_name=workflow.name,
                        execution_id=context.execution_id,
                        step_name=step.name,
                        error=exc,
                    ),
                    context
                )
                context.progress.fail(step.name, error=exc)
                raise exc

        logger.info(
            "workflow/executor/%s: successfully completed workflow '%s'",
            context.execution_id,
            workflow.name,
        )
        return last_result
