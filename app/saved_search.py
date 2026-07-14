"""Saved searches manager for hiring-radar.

Saves and runs combinations of sources, profiles, and CLI filter overrides.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import orjson
from pydantic import BaseModel

from app.config import settings


class SavedSearch(BaseModel):
    """Configuration for a named search query."""
    name: str
    profile: Optional[str] = None
    sources: list[str]
    remote: Optional[bool] = None
    country: Optional[str] = None
    keyword: Optional[str] = None
    exclude: Optional[str] = None
    days: Optional[int] = None
    limit: int


def _get_filepath() -> Path:
    return settings.output_dir / "saved_searches.json"


def load_saved_searches() -> dict[str, SavedSearch]:
    """Read saved searches from output/saved_searches.json."""
    path = _get_filepath()
    if not path.exists():
        return {}

    try:
        raw = path.read_bytes()
        if not raw:
            return {}
        data = orjson.loads(raw)
        if not isinstance(data, dict):
            return {}
        return {name: SavedSearch.model_validate(val) for name, val in data.items()}
    except Exception:
        # Gracefully handle corrupted or missing config by returning empty
        return {}


def save_saved_searches(searches: dict[str, SavedSearch]) -> None:
    """Write all saved searches back to output/saved_searches.json."""
    path = _get_filepath()
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = {name: s.model_dump(mode="json") for name, s in searches.items()}
    path.write_bytes(orjson.dumps(serialized, option=orjson.OPT_INDENT_2))
