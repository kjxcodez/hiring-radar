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

    def insert_many(self, companies: list[Company]) -> None:
        """Insert multiple companies, skipping duplicates based on dedupe_key."""
        existing = self.load_all()
        existing_keys = {c.dedupe_key() for c in existing}
        to_add = [c for c in companies if c.dedupe_key() not in existing_keys]
        if to_add:
            self.save_all(existing + to_add)

    def update_many(self, companies: list[Company]) -> None:
        """Update multiple existing companies in the database."""
        existing = self.load_all()
        by_key = {c.dedupe_key(): c for c in existing}
        updated = False
        for c in companies:
            key = c.dedupe_key()
            if key in by_key:
                by_key[key] = c
                updated = True
        if updated:
            self.save_all(list(by_key.values()))

    def delete_many(self, companies: list[Company]) -> None:
        """Remove multiple companies from the database."""
        existing = self.load_all()
        keys_to_delete = {c.dedupe_key() for c in companies}
        remaining = [c for c in existing if c.dedupe_key() not in keys_to_delete]
        if len(remaining) < len(existing):
            self.save_all(remaining)

    def upsert_many(self, companies: list[Company]) -> None:
        """Insert or update multiple companies based on dedupe_key."""
        existing = self.load_all()
        by_key = {c.dedupe_key(): c for c in existing}
        for c in companies:
            by_key[c.dedupe_key()] = c
        self.save_all(list(by_key.values()))

