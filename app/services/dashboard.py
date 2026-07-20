from __future__ import annotations

from pathlib import Path
from typing import Optional
from app.repositories import CompanyRepository
from app.dashboard.build import build_dashboard
from app.config import Settings

class DashboardService:
    def __init__(self, company_repo: CompanyRepository, settings: Settings):
        self.company_repo = company_repo
        self.settings = settings

    def generate_dashboard(self, output_path: Path, input_path: Optional[Path] = None) -> None:
        """Compile dashboard components, styles, scripts and embed the database JSON."""
        db_path = input_path or (self.settings.output_dir / "companies.json")
        build_dashboard(input_path=db_path, output_path=output_path)
