from __future__ import annotations

from pathlib import Path
import orjson
from app.models import Company
from app.exceptions import CompanyNotFoundError, MultipleCompaniesFoundError


class CompanyRepository:
    def __init__(self, filepath: Path):
        self.filepath = filepath

    def load_all(self) -> list[Company]:
        """Read all companies from the database, returning parsed models."""
        if not self.filepath.exists():
            return []
        try:
            raw = self.filepath.read_bytes()
            if not raw:
                return []
            return [Company.model_validate(c) for c in orjson.loads(raw)]
        except Exception:
            return []

    def save_all(self, companies: list[Company]) -> None:
        """Serialize and write all companies back to the JSON file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.write_bytes(
            orjson.dumps(
                [c.model_dump(mode="json") for c in companies],
                option=orjson.OPT_INDENT_2,
            )
        )

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
