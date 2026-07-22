"""Workflow Engine coordinating multi-step pipelines and lifecycle management."""

from __future__ import annotations

import logging
from typing import Any, Callable

from app.workflows.context import WorkflowContext
from app.workflows.events import (
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
)
from app.workflows.registry import get_workflow_class

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Central engine responsible for instantiating, running, and managing workflows.

    Coordinates execution, manages execution state, handles telemetry subscription
    listeners, and supports runtime cancellation.
    """

    def __init__(
        self,
        container: Any = None,
        settings: Any = None,
        ai_gateway: Any = None,
    ) -> None:
        self.container = container
        self.settings = settings or (container.settings if container else None)
        self.ai_gateway = ai_gateway or (container.ai_gateway if container else None)
        self.active_contexts: dict[str, WorkflowContext] = {}
        self.event_listeners: list[Callable[[Any], None]] = []

    def register_event_listener(self, listener: Callable[[Any], None]) -> None:
        """Register a callback that receives workflow lifecycle events."""
        self.event_listeners.append(listener)

    def _emit(self, event: Any) -> None:
        """Dispatch a workflow event to registered listeners."""
        for listener in self.event_listeners:
            try:
                listener(event)
            except Exception:  # noqa: S110
                pass

    def run(self, workflow_name: str, context: WorkflowContext | None = None, **kwargs: Any) -> Any:
        """Instantiate and execute the specified workflow.

        Args:
            workflow_name: Alias of the registered workflow (e.g. 'discover').
            context: Optional custom execution context override.
            **kwargs: Extra parameters merged into context metadata.

        Returns:
            The return value of the final step of the executed workflow.
        """
        workflow_cls = get_workflow_class(workflow_name)
        workflow = workflow_cls()

        if context is None:
            context = WorkflowContext(
                settings=self.settings,
                container=self.container,
                ai_gateway=self.ai_gateway,
                metadata=kwargs,
                event_dispatcher=self._emit,
            )
        else:
            context.metadata.update(kwargs)
            if context.event_dispatcher is None:
                context.event_dispatcher = self._emit

        self.active_contexts[context.execution_id] = context

        # Emit WorkflowStarted
        self._emit(
            WorkflowStarted(
                workflow_name=workflow.name,
                execution_id=context.execution_id,
                metadata=context.metadata,
            )
        )

        try:
            result = workflow.run(context)

            # Emit WorkflowCompleted
            self._emit(
                WorkflowCompleted(
                    workflow_name=workflow.name,
                    execution_id=context.execution_id,
                    result=result,
                )
            )
            return result

        except Exception as exc:
            # Emit WorkflowFailed
            self._emit(
                WorkflowFailed(
                    workflow_name=workflow.name,
                    execution_id=context.execution_id,
                    error=exc,
                )
            )
            raise exc
        finally:
            self.active_contexts.pop(context.execution_id, None)

    def cancel(self, execution_id: str) -> bool:
        """Set the cancellation flag for an active workflow execution.

        Args:
            execution_id: Unique UUID of the target execution context.

        Returns:
            True if target execution was active and marked for cancellation, else False.
        """
        context = self.active_contexts.get(execution_id)
        if context:
            context.cancelled = True
            logger.info("workflow/engine: execution '%s' marked for cancellation", execution_id)
            return True
        return False

    def resume(self, execution_id: str) -> Any:
        """Placeholder for future resumable/suspended executions."""
        raise NotImplementedError("Workflow resumption is not supported in this version.")
