from __future__ import annotations

from typing import Any
import pytest
from app.workflows.context import WorkflowContext
from app.workflows.engine import WorkflowEngine
from app.workflows.events import (
    WorkflowStarted,
    WorkflowCompleted,
    WorkflowFailed,
    StepStarted,
    StepFinished,
    StepFailed,
)
from app.workflows.step import WorkflowStep
from app.workflows.workflow import Workflow


class SuccessStep(WorkflowStep):
    name = "SuccessStep"
    description = "Step that succeeds"

    def execute(self, context: Any) -> str:
        context.metadata["step_run"] = True
        return "success_val"


class FailingStep(WorkflowStep):
    name = "FailingStep"
    description = "Step that fails"

    def execute(self, context: Any) -> Any:
        raise ValueError("Step failed intentionally")


class DummyWorkflow(Workflow):
    name = "dummy"
    description = "Dummy success workflow"
    steps = [SuccessStep()]


class DummyFailingWorkflow(Workflow):
    name = "dummy_failing"
    description = "Dummy failing workflow"
    steps = [FailingStep()]


@pytest.fixture
def test_engine():
    engine = WorkflowEngine()
    # Temporarily register dummy workflows on the map for tests
    from app.workflows.registry import _WORKFLOW_MAP
    _WORKFLOW_MAP["dummy"] = DummyWorkflow
    _WORKFLOW_MAP["dummy_failing"] = DummyFailingWorkflow
    yield engine
    # Cleanup dummy registrations
    _WORKFLOW_MAP.pop("dummy", None)
    _WORKFLOW_MAP.pop("dummy_failing", None)


def test_workflow_engine_execution_success(test_engine):
    events = []
    test_engine.register_event_listener(events.append)

    res = test_engine.run("dummy")
    assert res == "success_val"
    assert len(events) == 4

    assert isinstance(events[0], WorkflowStarted)
    assert isinstance(events[1], StepStarted)
    assert isinstance(events[2], StepFinished)
    assert isinstance(events[3], WorkflowCompleted)
    assert events[3].result == "success_val"


def test_workflow_engine_execution_failure(test_engine):
    events = []
    test_engine.register_event_listener(events.append)

    with pytest.raises(ValueError, match="Step failed intentionally"):
        test_engine.run("dummy_failing")

    assert len(events) == 4
    assert isinstance(events[0], WorkflowStarted)
    assert isinstance(events[1], StepStarted)
    assert isinstance(events[2], StepFailed)
    assert isinstance(events[3], WorkflowFailed)


def test_workflow_cancellation(test_engine):
    from app.workflows.progress import WorkflowProgress
    progress = WorkflowProgress()

    context = WorkflowContext(
        settings=None,
        container=None,
        progress=progress,
    )

    # Cancel context before execution
    context.cancelled = True

    with pytest.raises(RuntimeError, match="Workflow execution was cancelled."):
        test_engine.run("dummy", context=context)


def test_workflow_progress_events(test_engine):
    progress_updates = []

    def progress_callback(event_type: str, data: dict[str, Any]) -> None:
        progress_updates.append((event_type, data))

    from app.workflows.progress import WorkflowProgress
    progress = WorkflowProgress()
    progress.subscribe(progress_callback)

    context = WorkflowContext(
        settings=None,
        container=None,
        progress=progress,
    )

    test_engine.run("dummy", context=context)

    # progress emits start and complete for the step
    assert len(progress_updates) == 2
    assert progress_updates[0][0] == "start"
    assert progress_updates[0][1]["step_name"] == "SuccessStep"
    assert progress_updates[1][0] == "complete"
    assert progress_updates[1][1]["step_name"] == "SuccessStep"
