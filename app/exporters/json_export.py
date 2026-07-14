"""JSON export module for hiring-radar.

Exports processed company data structured as a JSON array using orjson.
"""

from __future__ import annotations

from pathlib import Path

import orjson

from app.models import Company


def export_json(companies: list[Company], output_path: Path) -> None:
    """Export a list of companies to a pretty-printed JSON file.

    Args:
        companies: List of Company objects to export.
        output_path: Destination path for the JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = [c.model_dump(mode="json") for c in companies]
    output_path.write_bytes(
        orjson.dumps(data, option=orjson.OPT_INDENT_2)
    )
