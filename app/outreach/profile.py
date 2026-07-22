"""Outreach and CRM data models for candidate tracking workflows."""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OutreachMessage(BaseModel):
    """An outreach message draft or sent log."""

    channel: str  # "email", "linkedin", "referral"
    subject: Optional[str] = None
    content: str
    generated_at: str
    user_approved: bool = False
    sent_at: Optional[str] = None


class Recruiter(BaseModel):
    """Corporate recruiter contact details."""

    name: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    role: Optional[str] = None


class Referral(BaseModel):
    """Referral details for employee introductions."""

    name: Optional[str] = None
    connection: Optional[str] = None  # e.g. "Alumni", "Mutual connection"
    email: Optional[str] = None
    status: str = "pending"  # "pending", "contacted", "referred", "none"


class FollowUp(BaseModel):
    """A scheduled follow-up reminder event."""

    day: int  # Offset days from apply date
    action: str  # e.g. "Send email follow-up"
    template_name: str
    status: str = "pending"  # "pending", "completed", "skipped"


class TimelineEntry(BaseModel):
    """An event on the application timeline."""

    event: str  # e.g. "Applied", "Technical Interview Scheduled"
    description: str
    timestamp: str
    metadata: Dict[str, str] = Field(default_factory=dict)
