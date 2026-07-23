"""Structured agent experience events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentEvent:
    """Base class for all agent experience and terminal UX events."""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ThinkingEvent(AgentEvent):
    """Emitted when the agent is planning or reasoning."""
    message: str = "Thinking..."


@dataclass
class SearchingEvent(AgentEvent):
    """Emitted when searching opportunities."""
    message: str = "Searching opportunities..."


@dataclass
class ResearchEvent(AgentEvent):
    """Emitted when researching companies."""
    message: str = "Researching companies..."


@dataclass
class RecommendationEvent(AgentEvent):
    """Emitted when scoring/ranking candidate matches."""
    message: str = "Ranking matches..."


@dataclass
class ApplicationEvent(AgentEvent):
    """Emitted when managing applications or outreach drafts."""
    message: str = "Preparing outreach..."


@dataclass
class MonitoringEvent(AgentEvent):
    """Emitted when monitoring hiring activity or updates."""
    message: str = "Checking status..."


@dataclass
class ProgressEvent(AgentEvent):
    """General task progress update event."""
    task_name: str = ""
    status: str = "running"  # e.g., "running", "success", "fail"
    message: str = ""


@dataclass
class CompletedEvent(AgentEvent):
    """Emitted when an operation finishes successfully."""
    message: str = "Done"


@dataclass
class ErrorEvent(AgentEvent):
    """Emitted when an operation fails."""
    error: str = ""
    message: str = ""
