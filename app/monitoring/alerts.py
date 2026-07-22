"""Alerting system defining prioritized warning notifications."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.monitoring.events import ChangeEvent


class Alert(BaseModel):
    """A prioritized notification alert card."""

    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    severity: str  # "Critical", "High", "Medium", "Low", "Informational"
    company_name: str
    job_url: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    read: bool = False


class AlertEngine:
    """Evaluates change events to generate user-facing warnings."""

    @staticmethod
    def generate_alerts(events: List[ChangeEvent]) -> List[Alert]:
        alerts = []
        for ev in events:
            # 1. Salary Increases
            if ev.event_type == "SalaryChanged":
                alerts.append(
                    Alert(
                        title=f"Salary increased at {ev.company_name}",
                        description=f"Compensation adjusted from {ev.previous_value} to {ev.current_value}.",
                        severity="High",
                        company_name=ev.company_name,
                        job_url=ev.job_url,
                    )
                )

            # 2. Remote policy changes
            elif ev.event_type == "RemotePolicyChanged":
                alerts.append(
                    Alert(
                        title=f"Remote policy updated at {ev.company_name}",
                        description=f"Work style transition: {ev.previous_value} -> {ev.current_value}.",
                        severity="High",
                        company_name=ev.company_name,
                        job_url=ev.job_url,
                    )
                )

            # 3. New match opened
            elif ev.event_type == "JobCreated":
                alerts.append(
                    Alert(
                        title=f"New vacancy at {ev.company_name}",
                        description=f"Position opened: '{ev.current_value}'. Check recommendation match fit.",
                        severity="Medium",
                        company_name=ev.company_name,
                        job_url=ev.job_url,
                    )
                )

            # 4. Hiring Status changes
            elif ev.event_type == "HiringStatusChanged":
                status_desc = "started hiring" if ev.current_value == "True" else "paused hiring"
                severity_val = "Critical" if ev.current_value == "True" else "Medium"
                alerts.append(
                    Alert(
                        title=f"{ev.company_name} {status_desc}",
                        description=f"Company status changed from {ev.previous_value} to {ev.current_value}.",
                        severity=severity_val,
                        company_name=ev.company_name,
                    )
                )

            # 5. Recommendation fit changes
            elif ev.event_type == "RecommendationChanged":
                alerts.append(
                    Alert(
                        title=f"Recommendation match score updated for {ev.company_name}",
                        description=f"Score shifted from {ev.previous_value} to {ev.current_value}.",
                        severity="High",
                        company_name=ev.company_name,
                        job_url=ev.job_url,
                    )
                )

            # 6. CRM Application stage changes
            elif ev.event_type == "ApplicationStatusChanged":
                alerts.append(
                    Alert(
                        title=f"Application stage updated for {ev.company_name}",
                        description=f"Stage moved: {ev.previous_value} -> {ev.current_value}.",
                        severity="Medium",
                        company_name=ev.company_name,
                        job_url=ev.job_url,
                    )
                )

        return alerts
