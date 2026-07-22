"""Fingerprinting module for creating deterministic checksums of CRM entities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.sync.fingerprint import generate_company_fingerprint, generate_job_fingerprint
from app.models import Application


class FingerprintEngine:
    """Generates stable SHA256 hashes of entities to detect changes."""

    @staticmethod
    def hash_string(data: str) -> str:
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @classmethod
    def company(cls, company: Any) -> str:
        return generate_company_fingerprint(company)

    @classmethod
    def job(cls, job: Any) -> str:
        return generate_job_fingerprint(job)

    @classmethod
    def intelligence(cls, intel: Any) -> str:
        """Hash company intelligence profile fields."""
        if not intel:
            return ""
        # Convert Pydantic model to json string in a stable sorted key layout
        if hasattr(intel, "model_dump_json"):
            return cls.hash_string(intel.model_dump_json())
        return cls.hash_string(json.dumps(intel, default=str, sort_keys=True))

    @classmethod
    def recommendation(cls, rec: dict) -> str:
        """Hash recommendation values."""
        # Focus on rank, score, job details, and explanation
        key_fields = {
            "rank": rec.get("rank"),
            "score": rec.get("score"),
            "company_name": rec.get("company_name"),
            "job_title": rec.get("job_title"),
            "job_url": rec.get("job_url"),
            "explanation": rec.get("explanation"),
        }
        return cls.hash_string(json.dumps(key_fields, sort_keys=True))

    @classmethod
    def application(cls, app: Application) -> str:
        """Hash CRM Application tracking status and timeline size."""
        key_fields = {
            "company_key": app.company_key,
            "status": app.status,
            "applied_date": str(app.applied_date) if app.applied_date else "",
            "last_contact_date": str(app.last_contact_date) if app.last_contact_date else "",
            "timeline_length": len(app.timeline) if app.timeline else 0,
            "next_followup": app.next_followup or "",
        }
        return cls.hash_string(json.dumps(key_fields, sort_keys=True))

    @classmethod
    def graph(cls, graph_path: Path) -> str:
        """Hash knowledge graph structure file."""
        if not graph_path.exists():
            return ""
        content = graph_path.read_text(encoding="utf-8")
        return cls.hash_string(content)
