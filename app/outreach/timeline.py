"""Timeline manager tracking stages and manually logged events."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional

from app.outreach.profile import TimelineEntry

if TYPE_CHECKING:
    from app.models import Application


class TimelineTracker:
    """Helper to log event updates to the application timeline."""

    @staticmethod
    def log_event(
        application: Application,
        event: str,
        description: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Append a new TimelineEntry to the application's timeline list."""
        entry = TimelineEntry(
            event=event,
            description=description,
            timestamp=datetime.utcnow().isoformat(),
            metadata=metadata or {},
        )
        if not hasattr(application, "timeline") or application.timeline is None:
            application.timeline = []
        
        application.timeline.append(entry)
        application.last_updated = datetime.utcnow()
