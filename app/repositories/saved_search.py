"""Repository for loading and saving SavedSearch definitions."""

from __future__ import annotations

from pathlib import Path
from app.saved_search import SavedSearch
from app.storage import JsonStorage


class SavedSearchRepository:
    """Repository handling persistence of saved search configurations using JsonStorage."""

    def __init__(self, filepath: Path, storage: JsonStorage | None = None):
        self.filepath = filepath
        self.storage = storage or JsonStorage()

    def load_all(self) -> dict[str, SavedSearch]:
        """Read all saved searches from the JSON file."""
        try:
            data = self.storage.read(self.filepath)
            if not data or not isinstance(data, dict):
                return {}
            return {name: SavedSearch.model_validate(val) for name, val in data.items()}
        except Exception:
            return {}

    def save_all(self, searches: dict[str, SavedSearch]) -> None:
        """Write all saved searches back to the JSON file."""
        serialized = {name: s.model_dump(mode="json") for name, s in searches.items()}
        self.storage.write(self.filepath, serialized)
