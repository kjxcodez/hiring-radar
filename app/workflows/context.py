"""Execution state and context provider for workflows."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.workflows.progress import WorkflowProgress


class WorkflowContext:
    """Carries setting values, service container registry, and transient state.

    Decouples individual pipeline steps from referencing global variables,
    allowing thread-safe execution, easy unit test mocking, and future background worker support.
    """

    def __init__(
        self,
        settings: Any,
        container: Any,
        ai_gateway: Any = None,
        progress: WorkflowProgress | None = None,
        metadata: dict[str, Any] | None = None,
        execution_id: str | None = None,
        logger: logging.Logger | None = None,
        event_dispatcher: Callable[[Any], None] | None = None,
    ) -> None:
        self.settings = settings
        self.container = container
        self.ai_gateway = ai_gateway
        self.progress = progress or WorkflowProgress()
        self.metadata = metadata or {}
        self.execution_id = execution_id or str(uuid.uuid4())
        self.logger = logger or logging.getLogger(f"workflow.{self.execution_id}")
        self.cancelled = False
        self.event_dispatcher = event_dispatcher

    @property
    def repositories(self) -> Any:
        """Expose dependency container for repository access compatibility."""
        return self.container

    @property
    def services(self) -> Any:
        """Expose dependency container for lazy service access compatibility."""
        return self.container
