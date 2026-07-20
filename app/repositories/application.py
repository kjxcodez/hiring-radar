from __future__ import annotations

from pathlib import Path
import orjson
from app.models import Application

class ApplicationRepository:
    def __init__(self, filepath: Path):
        self.filepath = filepath

    def load_all(self) -> dict[str, Application]:
        """Read all applications, returning a mapping keyed by Company.dedupe_key()."""
        from app.tracker.status import load_applications
        return load_applications(self.filepath)

    def save_all(self, apps: dict[str, Application]) -> None:
        """Write all applications back to the JSON file."""
        from app.tracker.status import save_applications
        save_applications(apps, self.filepath)
