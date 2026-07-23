"""Schemas and management definitions for task graphs and execution nodes."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class Task(BaseModel):
    """A single execution node inside an agent workflow graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    dependencies: List[str] = Field(default_factory=list)
    priority: int = 0
    estimated_cost: float = 0.0
    estimated_tokens: int = 0
    retry_policy: Dict[str, Any] = Field(default_factory=dict)
    timeout: int = 300
    status: TaskStatus = TaskStatus.PENDING
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None


class TaskGraph(BaseModel):
    """Graph of dependency tasks executed by the autonomous agent runtime."""
    graph_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    tasks: Dict[str, Task] = Field(default_factory=dict)

    def add_task(self, task: Task) -> None:
        """Register a task node in the graph."""
        self.tasks[task.id] = task

    def get_runnable_tasks(self) -> List[Task]:
        """Return tasks that have no outstanding unresolved dependencies."""
        runnable = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
                
            deps_ok = True
            for dep_id in task.dependencies:
                dep_task = self.tasks.get(dep_id)
                if not dep_task or dep_task.status != TaskStatus.SUCCEEDED:
                    deps_ok = False
                    break
                    
            if deps_ok:
                runnable.append(task)
        return runnable

    def is_completed(self) -> bool:
        """Check if all nodes in the graph succeeded."""
        return all(t.status == TaskStatus.SUCCEEDED for t in self.tasks.values())

    def is_failed(self) -> bool:
        """Check if any nodes in the graph failed and cannot be retried."""
        return any(t.status == TaskStatus.FAILED for t in self.tasks.values())
