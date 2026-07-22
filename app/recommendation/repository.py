"""Repository layer managing persistent recommendation records."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.storage import JsonStorage


class RecommendationRepository:
    """Handles read and write serialization for candidate job recommendations."""

    def __init__(self, filepath: Path, storage: Optional[JsonStorage] = None) -> None:
        self.filepath = filepath
        self.storage = storage or JsonStorage()

    def save_recommendations(self, recommendations: List[Dict[str, Any]]) -> None:
        """Atomically persist recommendation records to disk."""
        self.storage.write(self.filepath, recommendations)

    def load_recommendations(self) -> List[Dict[str, Any]]:
        """Load and deserialize recommendation records."""
        if not self.storage.exists(self.filepath):
            return []
        try:
            data = self.storage.read(self.filepath)
            if data and isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def find_by_job_url(self, job_url: str) -> Optional[Dict[str, Any]]:
        """Lookup a recommendation by its job url."""
        recs = self.load_recommendations()
        for r in recs:
            if r.get("job_url") == job_url:
                return r
        return None

    def clear(self) -> None:
        """Clear all stored recommendations from disk."""
        if self.storage.exists(self.filepath):
            self.storage.delete(self.filepath)
