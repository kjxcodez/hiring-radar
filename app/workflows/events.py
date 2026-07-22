"""Execution lifecycle events emitted by the Workflow Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WorkflowEvent:
    """Base class for all workflow execution lifecycle events."""
    workflow_name: str
    execution_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkflowStarted(WorkflowEvent):
    """Emitted when a workflow begins execution."""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowCompleted(WorkflowEvent):
    """Emitted when a workflow finishes successfully."""
    result: Any = None


@dataclass
class WorkflowFailed(WorkflowEvent):
    """Emitted when a workflow fails due to an error."""
    error: Exception | None = None


@dataclass
class StepEvent(WorkflowEvent):
    """Base class for step-level events."""
    step_name: str = ""


@dataclass
class StepStarted(StepEvent):
    """Emitted when a workflow step begins execution."""
    pass


@dataclass
class StepFinished(StepEvent):
    """Emitted when a workflow step completes successfully."""
    result: Any = None


@dataclass
class StepFailed(StepEvent):
    """Emitted when a workflow step fails."""
    error: Exception | None = None
