"""Search profiles module for hiring-radar.

Provides models and loaders for YAML-based search profiles to filter companies and job postings.
"""

from __future__ import annotations

from pathlib import Path
import yaml
from pydantic import BaseModel, Field


class SearchProfile(BaseModel):
    """A search profile containing keywords, location filters, and exclusions.

    Example configuration is located at `profiles/frontend.yaml`.
    """
    name: str
    keywords: list[str] = Field(default_factory=list)
    remote: bool | None = None
    countries: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


def list_profiles() -> list[str]:
    """Return all profile names found in profiles/*.yaml (stem of filename)."""
    profiles_dir = Path("profiles")
    if not profiles_dir.exists():
        return []
    return [p.stem for p in profiles_dir.glob("*.yaml")]


def load_profile(name: str) -> SearchProfile:
    """Read profiles/{name}.yaml via PyYAML and validate it into a SearchProfile.

    Raises FileNotFoundError with a list of available profiles if the requested
    profile is missing.
    """
    profiles_dir = Path("profiles")
    profile_path = profiles_dir / f"{name}.yaml"

    if not profile_path.exists():
        available = list_profiles()
        available_str = ", ".join(f"'{p}'" for p in available) if available else "none"
        raise FileNotFoundError(
            f"Search profile '{name}' not found at {profile_path}.\n"
            f"Available profiles: {available_str}"
        )

    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        raise ValueError(f"Failed to parse YAML file at {profile_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Invalid search profile data in {profile_path}, expected dictionary.")

    # Ensure name is set if missing in YAML file
    if "name" not in data:
        data["name"] = name

    return SearchProfile.model_validate(data)


def load_alert_rules(path: Path = Path("alerts.yaml")) -> list[SearchProfile]:
    """Read alerts.yaml and validate it into a list of SearchProfile rules.

    If the file does not exist, logs an info message pointing to
    alerts.example.yaml and returns an empty list.
    """
    from loguru import logger
    if not path.exists():
        logger.info(
            "Alerts file '{path}' not found. To configure, copy alerts.example.yaml to alerts.yaml "
            "and adjust rules.", path=str(path)
        )
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Failed to parse alerts YAML file at {path}: {exc}", path=str(path), exc=exc)
        return []

    if not isinstance(data, list):
        logger.warning("Invalid alerts data in {path}, expected a list of rule dictionaries.", path=str(path))
        return []

    rules = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning("Skipping rule {idx} in {path}: expected a dictionary.", idx=idx, path=str(path))
            continue
        # Ensure a name is set
        if "name" not in item:
            item["name"] = f"rule-{idx}"
        try:
            rules.append(SearchProfile.model_validate(item))
        except Exception as exc:
            logger.warning("Skipping invalid rule {idx} in {path}: {exc}", idx=idx, path=str(path), exc=exc)

    return rules

