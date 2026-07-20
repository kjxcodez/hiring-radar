from __future__ import annotations

from pathlib import Path
import yaml
from app.profiles import SearchProfile

class ProfileRepository:
    def __init__(self, profiles_dir: Path, alerts_path: Path):
        self.profiles_dir = profiles_dir
        self.alerts_path = alerts_path

    def list_profiles(self) -> list[str]:
        """Return the stems of all available profile YAML files."""
        if not self.profiles_dir.exists():
            return []
        return [p.stem for p in self.profiles_dir.glob("*.yaml")]

    def load_profile(self, name: str) -> SearchProfile:
        """Parse the specific profile config, raising FileNotFoundError if missing."""
        profile_path = self.profiles_dir / f"{name}.yaml"
        if not profile_path.exists():
            available = self.list_profiles()
            available_str = ", ".join(f"'{p}'" for p in available) if available else "none"
            raise FileNotFoundError(
                f"Search profile '{name}' not found at {profile_path}.\n"
                f"Available profiles: {available_str}"
            )
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Invalid search profile data in {profile_path}, expected dictionary.")
        if "name" not in data:
            data["name"] = name
        return SearchProfile.model_validate(data)

    def load_alert_rules(self) -> list[SearchProfile]:
        """Parse rules in alerts.yaml, returning an empty list if file is missing/invalid."""
        if not self.alerts_path.exists():
            return []
        try:
            with open(self.alerts_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        rules = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            if "name" not in item:
                item["name"] = f"rule-{idx}"
            try:
                rules.append(SearchProfile.model_validate(item))
            except Exception:
                continue
        return rules
