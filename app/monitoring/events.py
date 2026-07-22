"""Change detection event models representing adjustments in companies, jobs, recommendations, and CRM statuses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ChangeEvent(BaseModel):
    """Base model for all change detection events."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    company_name: str
    job_url: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    previous_value: Optional[Any] = None
    current_value: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "Informational"  # "Critical", "High", "Medium", "Low", "Informational"


class JobCreated(ChangeEvent):
    event_type: str = "JobCreated"
    severity: str = "Medium"


class JobClosed(ChangeEvent):
    event_type: str = "JobClosed"
    severity: str = "Medium"


class JobUpdated(ChangeEvent):
    event_type: str = "JobUpdated"
    severity: str = "Low"


class SalaryChanged(ChangeEvent):
    event_type: str = "SalaryChanged"
    severity: str = "High"


class LocationChanged(ChangeEvent):
    event_type: str = "LocationChanged"
    severity: str = "Low"


class RemotePolicyChanged(ChangeEvent):
    event_type: str = "RemotePolicyChanged"
    severity: str = "High"


class HiringStatusChanged(ChangeEvent):
    event_type: str = "HiringStatusChanged"
    severity: str = "High"


class EngineeringStackChanged(ChangeEvent):
    event_type: str = "EngineeringStackChanged"
    severity: str = "Medium"


class RecruiterChanged(ChangeEvent):
    event_type: str = "RecruiterChanged"
    severity: str = "Low"


class RecommendationChanged(ChangeEvent):
    event_type: str = "RecommendationChanged"
    severity: str = "High"


class ApplicationStatusChanged(ChangeEvent):
    event_type: str = "ApplicationStatusChanged"
    severity: str = "High"
