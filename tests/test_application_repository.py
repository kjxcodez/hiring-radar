"""Unit tests for the ApplicationRepository persistent layer."""

from __future__ import annotations

from pathlib import Path
from app.models import Application
from app.storage import JsonStorage
from app.repositories.application import ApplicationRepository


def test_application_repository_save_load(tmp_path: Path):
    filepath = tmp_path / "applications.json"
    repo = ApplicationRepository(filepath, JsonStorage())

    # Initially empty or non-existent
    assert repo.load_all() == {}

    # Save application
    app = Application(
        company_key="stripe.com",
        status="Prepared",
    )
    repo.save_all({"stripe.com": app})

    # Load and verify
    loaded = repo.load_all()
    assert "stripe.com" in loaded
    assert loaded["stripe.com"].status == "Prepared"
