from __future__ import annotations

from pathlib import Path
from app.models import Application
from app.storage import JsonStorage


class ApplicationRepository:
    """Repository managing Application entity persistence using JsonStorage via tracker status helpers."""

    def __init__(self, filepath: Path, storage: JsonStorage | None = None):
        self.filepath = filepath
        self.storage = storage or JsonStorage()

    def load_all(self) -> dict[str, Application]:
        """Read all applications, returning a mapping keyed by Company.dedupe_key()."""
        from app.tracker.status import load_applications
        return load_applications(self.filepath)

    def save_all(self, apps: dict[str, Application]) -> None:
        """Write all applications back to the JSON file."""
        from app.tracker.status import save_applications
        save_applications(apps, self.filepath)
