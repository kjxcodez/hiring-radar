from __future__ import annotations

from pathlib import Path
from typing import Any
import orjson

class MemoryRepository:
    def __init__(self, filepath: Path):
        self.filepath = filepath

    def load(self) -> dict[str, Any]:
        """Read agent memory structure or return empty defaults."""
        if not self.filepath.exists():
            return {
                "preferences": {},
                "rejected_companies": [],
                "past_decisions": []
            }
        try:
            raw = self.filepath.read_bytes()
            if not raw:
                return {
                    "preferences": {},
                    "rejected_companies": [],
                    "past_decisions": []
                }
            return orjson.loads(raw)
        except Exception:
            return {
                "preferences": {},
                "rejected_companies": [],
                "past_decisions": []
            }

    def save(self, memory: dict[str, Any]) -> None:
        """Write agent memory structure back to file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.write_bytes(orjson.dumps(memory, option=orjson.OPT_INDENT_2))
