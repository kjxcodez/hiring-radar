"""Monitoring Cache managing entity hash comparisons and tracking cache state."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
from app.storage import JsonStorage


class MonitoringCache:
    """Tracks entity fingerprints to allow incremental change checks."""

    def __init__(self, cache_path: Path, storage: Optional[JsonStorage] = None):
        self.cache_path = cache_path
        self.storage = storage or JsonStorage()
        self._cache: Dict[str, str] = {}
        self.load()

    def load(self) -> None:
        """Load fingerprints from file."""
        if self.cache_path.exists():
            try:
                self._cache = self.storage.read(self.cache_path) or {}
            except Exception:  # noqa: BLE001
                self._cache = {}

    def save(self) -> None:
        """Write current cache to file."""
        self.storage.write(self.cache_path, self._cache)

    def is_unchanged(self, entity_id: str, new_hash: str) -> bool:
        """Return True if the entity is unchanged and update the cache."""
        old_hash = self._cache.get(entity_id)
        if old_hash == new_hash:
            return True
        self._cache[entity_id] = new_hash
        return False

    def clear(self) -> None:
        """Wipe cache."""
        self._cache = {}
        if self.cache_path.exists():
            self.cache_path.unlink()
