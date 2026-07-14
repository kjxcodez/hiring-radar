"""Template engine for cold email outreach.

Allows listing, loading, and rendering of markdown-based email body templates
using simple double-brace placeholders (e.g. {{recipient_name}}).
"""

from __future__ import annotations

import re
from pathlib import Path


def list_templates() -> list[str]:
    """Return all template names found in templates/*.md (stem of filename)."""
    templates_dir = Path("templates")
    if not templates_dir.exists():
        return []
    return [p.stem for p in templates_dir.glob("*.md")]


def load_template(name: str) -> str:
    """Read templates/{name}.md and return the raw text content.

    Raises FileNotFoundError with available templates if missing.
    """
    templates_dir = Path("templates")
    template_path = templates_dir / f"{name}.md"

    if not template_path.exists():
        available = list_templates()
        available_str = ", ".join(f"'{t}'" for t in available) if available else "none"
        raise FileNotFoundError(
            f"Outreach template '{name}' not found at {template_path}.\n"
            f"Available templates: {available_str}"
        )

    try:
        return template_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise OSError(f"Failed to read template file at {template_path}: {exc}") from exc


def render_template(template_text: str, values: dict[str, str]) -> str:
    """Substitute placeholders like {{key}} with values from the dictionary.

    Unmatched placeholders remain in the output as {{key}} so the user can easily
    notice missing variables.
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        # Return the value if present, otherwise keep the placeholder intact
        return values.get(key, match.group(0))

    # Match {{placeholder_name}} pattern
    return re.sub(r"\{\{([^}]+)\}\}", replacer, template_text)
