from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid

from app.runtime.state import ExecutionStatus
from app.runtime.triggers import TriggerSource


class Execution(BaseModel):
    """Represents a single workflow execution instance tracking lifecycle, metrics, and results."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str
    status: ExecutionStatus = ExecutionStatus.QUEUED
    trigger: TriggerSource = TriggerSource.MANUAL
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
