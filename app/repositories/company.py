from __future__ import annotations

from pathlib import Path
from app.models import Company
from app.exceptions import CompanyNotFoundError, MultipleCompaniesFoundError
from app.storage import JsonStorage


class CompanyRepository:
    """Repository managing Company entity persistence using JsonStorage."""

    def __init__(self, filepath: Path, storage: JsonStorage | None = None):
        self.filepath = filepath
        self.storage = storage or JsonStorage()

    def load_all(self) -> list[Company]:
        """Read all companies from the database, returning parsed models."""
        try:
            data = self.storage.read(self.filepath)
            if not data or not isinstance(data, list):
                return []
            return [Company.model_validate(c) for c in data]
        except Exception:
            return []

    def save_all(self, companies: list[Company]) -> None:
        """Serialize and write all companies back to the JSON file."""
        data = [c.model_dump(mode="json") for c in companies]
        self.storage.write(self.filepath, data)

    def find_by_name(self, name: str) -> Company:
        """Find a unique company by name substring, raising domain exceptions if not unique."""
        all_companies = self.load_all()
        matches = [c for c in all_companies if name.lower() in c.name.lower()]
        if not matches:
            raise CompanyNotFoundError(f"Company '{name}' not found.")
        if len(matches) > 1:
            raise MultipleCompaniesFoundError(
                f"Multiple companies match '{name}': "
                + ", ".join(c.name for c in matches)
            )
        return matches[0]
