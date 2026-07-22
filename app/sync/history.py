"""Synchronization history manager tracking detailed logs of past sync runs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from app.storage import JsonStorage


class SyncHistoryEntry(BaseModel):
    """A log entry of a single provider synchronization run."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    provider: str
    status: Literal["success", "failed"]
    duration: float = 0.0
    added_companies: int = 0
    updated_companies: int = 0
    removed_companies: int = 0
    added_jobs: int = 0
    updated_jobs: int = 0
    removed_jobs: int = 0
    error_message: Optional[str] = None


class SyncHistory:
    """Manages the persistence of synchronization history logs."""

    def __init__(self, filepath: Path, storage: Optional[JsonStorage] = None) -> None:
        self.filepath = filepath
        self.storage = storage or JsonStorage()

    def load_all(self) -> List[SyncHistoryEntry]:
        """Load the complete sync history log from JSON."""
        try:
            data = self.storage.read(self.filepath)
            if not data or not isinstance(data, list):
                return []
            return [SyncHistoryEntry.model_validate(e) for e in data]
        except Exception:
            return []

    def append(self, entry: SyncHistoryEntry) -> None:
        """Append a new synchronization history entry to log."""
        entries = self.load_all()
        entries.append(entry)
        data = [e.model_dump(mode="json") for e in entries]
        self.storage.write(self.filepath, data)

    def clear(self) -> None:
        """Wipe the sync history log file."""
        if self.storage.exists(self.filepath):
            self.storage.delete(self.filepath)
            
    def exists(self) -> bool:
        """Check if history log file exists."""
        return self.storage.exists(self.filepath)
