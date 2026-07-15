"""Lightweight persistent memory database for the AI Agent."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import orjson

from app.config import settings


def _get_memory_path() -> Path:
    return settings.output_dir / "agent_memory.json"


def load_memory() -> dict[str, Any]:
    """Load agent memory from output/agent_memory.json.

    Returns the default empty structure if the file does not exist.
    """
    path = _get_memory_path()
    if not path.exists():
        return {
            "preferences": {},
            "rejected_companies": [],
            "past_decisions": []
        }
    try:
        return orjson.loads(path.read_bytes())
    except Exception:  # noqa: BLE001
        return {
            "preferences": {},
            "rejected_companies": [],
            "past_decisions": []
        }


def save_memory(memory: dict[str, Any]) -> None:
    """Persist the memory dictionary back to output/agent_memory.json."""
    path = _get_memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(memory, option=orjson.OPT_INDENT_2))


def remember_preference(key: str, value: str) -> None:
    """Store or update a free-form preference mapping."""
    memory = load_memory()
    memory.setdefault("preferences", {})
    memory["preferences"][key] = value
    save_memory(memory)


def reject_company(company_key: str, reason: str) -> None:
    """Append a company to the list of rejected companies and logs a past decision."""
    memory = load_memory()
    memory.setdefault("rejected_companies", [])
    if company_key not in memory["rejected_companies"]:
        memory["rejected_companies"].append(company_key)

    decision = {
        "date": date.today().isoformat(),
        "summary": f"Rejected company '{company_key}'. Reason: {reason}"
    }
    memory.setdefault("past_decisions", [])
    memory["past_decisions"].append(decision)
    save_memory(memory)


def log_decision(summary: str) -> None:
    """Log an audit entry summary under past decisions history."""
    memory = load_memory()
    decision = {
        "date": date.today().isoformat(),
        "summary": summary
    }
    memory.setdefault("past_decisions", [])
    memory["past_decisions"].append(decision)
    save_memory(memory)
