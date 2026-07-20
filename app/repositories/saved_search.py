"""Repository for loading and saving SavedSearch definitions."""

from __future__ import annotations

from pathlib import Path
import orjson
from app.saved_search import SavedSearch


class SavedSearchRepository:
    """Repository handling persistence of saved search configurations."""

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def load_all(self) -> dict[str, SavedSearch]:
        """Read all saved searches from the JSON file."""
        if not self.filepath.exists():
            return {}

        try:
            raw = self.filepath.read_bytes()
            if not raw:
                return {}
            data = orjson.loads(raw)
            if not isinstance(data, dict):
                return {}
            return {name: SavedSearch.model_validate(val) for name, val in data.items()}
        except Exception:
            return {}

    def save_all(self, searches: dict[str, SavedSearch]) -> None:
        """Write all saved searches back to the JSON file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        serialized = {name: s.model_dump(mode="json") for name, s in searches.items()}
        self.filepath.write_bytes(orjson.dumps(serialized, option=orjson.OPT_INDENT_2))
