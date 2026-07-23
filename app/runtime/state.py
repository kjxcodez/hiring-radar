from enum import Enum


class ExecutionStatus(str, Enum):
    """The current state of a scheduled or queued workflow execution."""
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    FAILED = "failed"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
