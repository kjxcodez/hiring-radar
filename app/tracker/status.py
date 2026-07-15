"""State machine and persistence for job application tracking.

Handles loading/saving applications to applications.json and transitioning
application statuses with validation warnings.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import orjson
from loguru import logger

from app.models import Application, ApplicationStatus


_STATUS_ORDER = {
    "discovered": 1,
    "researched": 2,
    "applied": 3,
    "interviewing": 4,
    "rejected": 5,
    "offer": 5,
}


def load_applications(path: Path) -> dict[str, Application]:
    """Read applications from applications.json keyed by company_key.

    Returns an empty dict if the file does not exist.
    """
    if not path.exists():
        return {}

    try:
        data = orjson.loads(path.read_bytes())
        return {
            key: Application.model_validate(val)
            for key, val in data.items()
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load applications from {path}: {exc}. Returning empty database.", path=path, exc=exc)
        return {}


def save_applications(apps: dict[str, Application], path: Path) -> None:
    """Serialize the applications dictionary to applications.json."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            orjson.dumps(
                {key: app.model_dump(mode="json") for key, app in apps.items()},
                option=orjson.OPT_INDENT_2,
            )
        )
    except Exception as exc:
        logger.error("Failed to save applications to {path}: {exc}", path=path, exc=exc)
        raise exc


def set_status(
    apps: dict[str, Application],
    company_key: str,
    new_status: ApplicationStatus,
) -> Application:
    """Transition the application status for a company, creating the record if missing.

    Logs a warning if the transition goes backwards in the logical workflow order.
    """
    today = date.today()

    if company_key not in apps:
        # Create default record starting with "discovered"
        app = Application(
            company_key=company_key,
            status="discovered",
            status_history=[{"status": "discovered", "date": today.isoformat()}],
        )
        apps[company_key] = app
    else:
        app = apps[company_key]

    old_status = app.status

    # Validate logical flow sequence
    old_weight = _STATUS_ORDER.get(old_status, 0)
    new_weight = _STATUS_ORDER.get(new_status, 0)
    if new_weight < old_weight:
        logger.warning(
            "Backwards-nonsensical transition for company '{key}': '{old}' -> '{new}'",
            key=company_key,
            old=old_status,
            new=new_status,
        )

    # Set new status and record in history if changed
    app.status = new_status
    app.status_history.append({"status": new_status, "date": today.isoformat()})

    # Update date fields based on workflow
    if new_status in ("applied", "interviewing"):
        app.last_contact_date = today

    if new_status == "applied" and app.applied_date is None:
        app.applied_date = today

    return app
