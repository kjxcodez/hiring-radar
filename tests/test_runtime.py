"""Tests for autonomous agent runtime, task graphs, executors, and recovery."""

from __future__ import annotations

from pathlib import Path
import time
import pytest
from app.runtime.task import Task, TaskGraph, TaskStatus
from app.runtime.events import EventBus
from app.runtime.executor import GraphExecutor, classify_failure
from app.runtime.recovery import RecoveryEngine
from app.runtime.scheduler import Scheduler, ScheduledJob


def test_task_graph_runnable_nodes() -> None:
    """Verify TaskGraph retrieves runnable tasks with dependencies met."""
    graph = TaskGraph(goal="Test Graph Goal")
    
    t1 = Task(id="t1", name="Task 1", status=TaskStatus.SUCCEEDED)
    t2 = Task(id="t2", name="Task 2", status=TaskStatus.PENDING, dependencies=["t1"])
    t3 = Task(id="t3", name="Task 3", status=TaskStatus.PENDING, dependencies=["t2"])
    
    graph.add_task(t1)
    graph.add_task(t2)
    graph.add_task(t3)
    
    runnable = graph.get_runnable_tasks()
    assert len(runnable) == 1
    assert runnable[0].id == "t2"


def test_event_bus() -> None:
    """Verify EventBus subscriber gets triggered on publish."""
    bus = EventBus(history_limit=10)
    received = []
    
    def cb(event) -> None:
        received.append(event)
        
    bus.subscribe("Task Started", cb)
    bus.publish("Task Started", {"name": "Stripe scraper"})
    
    assert len(received) == 1
    assert received[0].data["name"] == "Stripe scraper"


def test_failure_classification() -> None:
    """Verify Exception classifying mapping helper."""
    assert classify_failure(TimeoutError("request timed out")) == "Network"
    assert classify_failure(ValueError("invalid arguments")) == "Validation"
    assert classify_failure(RuntimeError("429 rate limit exceeded")) == "Rate Limit"


def test_recovery_engine(tmp_path: Path) -> None:
    """Verify RecoveryEngine saves and loads active task graphs."""
    recovery = RecoveryEngine(directory=tmp_path)
    
    graph = TaskGraph(goal="Recover Goal")
    t1 = Task(id="t1", name="Recovery Task", status=TaskStatus.RUNNING)
    graph.add_task(t1)
    
    recovery.save_state({"g1": graph})
    
    recovered = recovery.load_state()
    assert "g1" in recovered
    assert recovered["g1"].goal == "Recover Goal"
    assert recovered["g1"].tasks["t1"].status == TaskStatus.RUNNING


def test_scheduler_calculations(tmp_path: Path) -> None:
    """Verify Scheduler calculates next run times correctly."""
    sched = Scheduler(schedule_file=tmp_path / "sched.json")
    
    job = ScheduledJob(
        id="j1",
        workflow_name="company_research",
        cron_or_interval="every_hour"
    )
    sched.calculate_next_run(job)
    assert job.next_run is not None
    assert (job.next_run - datetime_utcnow()).total_seconds() <= 3600


def datetime_utcnow() -> Any:
    import datetime
    return datetime.datetime.utcnow()
