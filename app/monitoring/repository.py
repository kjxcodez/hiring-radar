"""MonitoringRepository persistent storage for events, alerts, and daily digests."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
from app.storage import JsonStorage
from app.monitoring.events import ChangeEvent
from app.monitoring.alerts import Alert


class MonitoringRepository:
    """Handles JSON reading and writing of change intelligence data."""

    def __init__(
        self,
        events_path: Path,
        alerts_path: Path,
        digest_path: Path,
        storage: Optional[JsonStorage] = None,
    ):
        self.events_path = events_path
        self.alerts_path = alerts_path
        self.digest_path = digest_path
        self.storage = storage or JsonStorage()

    def save_events(self, events: List[ChangeEvent]) -> None:
        """Serialize and save all change events to JSON."""
        data = [e.model_dump(mode="json") for e in events]
        self.storage.write(self.events_path, data)

    def load_events(self) -> List[dict]:
        """Load and return all change events."""
        if not self.events_path.exists():
            return []
        return self.storage.read(self.events_path) or []

    def save_alerts(self, alerts: List[Alert]) -> None:
        """Serialize and save all alerts."""
        data = [a.model_dump(mode="json") for a in alerts]
        self.storage.write(self.alerts_path, data)

    def load_alerts(self) -> List[dict]:
        """Load and return all alerts."""
        if not self.alerts_path.exists():
            return []
        return self.storage.read(self.alerts_path) or []

    def save_digest(self, digest: dict) -> None:
        """Save the daily digest dict."""
        self.storage.write(self.digest_path, digest)

    def load_digest(self) -> dict:
        """Load and return the daily digest."""
        if not self.digest_path.exists():
            return {}
        return self.storage.read(self.digest_path) or {}

    def clear(self) -> None:
        """Clear all monitoring databases."""
        for path in [self.events_path, self.alerts_path, self.digest_path]:
            if path.exists():
                path.unlink()
