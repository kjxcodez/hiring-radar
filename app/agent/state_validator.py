"""State validation engine verifying consistency across Hiring Radar repositories."""

from __future__ import annotations

from app.cli.common import get_container
from app.config import settings


def validate_system_state() -> list[str]:
    """Audit all database repositories for potential cross-entity integrity warnings.

    Returns:
        List of human-readable warning strings. An empty list indicates perfectly synchronized state.
    """
    warnings = []
    container = get_container()

    # 1. Resume existence vs. Recommendations
    resume_exists = settings.resume_path and settings.resume_path.exists()
    try:
        recs = container.recommendation_repo.load_recommendations()
    except Exception:
        recs = []

    if recs and not resume_exists:
        warnings.append(
            "Stale recommendations exist in the database, but no active resume is currently loaded."
        )

    # 2. Company vs. Job postings consistency
    try:
        companies = container.company_repo.load_all()
    except Exception:
        companies = []

    total_jobs = sum(len(c.jobs) for c in companies)
    if not companies and total_jobs > 0:
        warnings.append("Database corruption detected: Job records exist, but company database is empty.")

    # 3. Application CRM references
    try:
        apps_data = container.application_repo.load_all()
        apps = apps_data.values() if isinstance(apps_data, dict) else apps_data
    except Exception:
        apps = []

    company_keys = {c.dedupe_key() for c in companies}
    for app in apps:
        co_key = getattr(app, "company_key", None) or app.get("company_key")
        if co_key and co_key not in company_keys:
            warnings.append(
                f"Application CRM record refers to company key '{co_key}', which does not exist in companies.json."
            )

    # 4. Monitoring Alerts references
    try:
        alerts = container.monitoring_repo.load_alerts()
    except Exception:
        alerts = []

    for alert in alerts:
        co_name = alert.get("company_name") if isinstance(alert, dict) else getattr(alert, "company_name", None)
        if co_name:
            matched = any(c.name.lower() == co_name.lower() for c in companies)
            if not matched and companies:
                warnings.append(
                    f"Monitoring Alert refers to company '{co_name}', which does not exist in the current companies database."
                )

    return warnings
