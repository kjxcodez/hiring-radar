from __future__ import annotations

from pathlib import Path
from typing import Any
from app.storage import JsonStorage


class MemoryRepository:
    """Repository managing Agent Memory entity persistence using JsonStorage."""

    def __init__(self, filepath: Path, storage: JsonStorage | None = None):
        self.filepath = filepath
        self.storage = storage or JsonStorage()

    def load(self) -> dict[str, Any]:
        """Read agent memory structure or return empty defaults."""
        default_val = {
            "preferences": {},
            "rejected_companies": [],
            "past_decisions": []
        }
        try:
            data = self.storage.read(self.filepath)
            if not data or not isinstance(data, dict):
                return default_val
            return data
        except Exception:
            return default_val

    def save(self, memory: dict[str, Any]) -> None:
        """Write agent memory structure back to file."""
        self.storage.write(self.filepath, memory)
