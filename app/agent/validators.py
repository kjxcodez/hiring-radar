"""Validation, error handling, and recovery strategies for the AI Agent."""

from __future__ import annotations

import logging
from typing import Any, Optional
from app.cli.common import get_container

logger = logging.getLogger(__name__)


def validate_tool_result(tool_name: str, result: Any) -> tuple[bool, str]:
    """Validate a tool execution result, returning (is_valid, user_facing_error).

    Guarantees the LLM is informed when results are empty so it cannot fabricate data.
    """
    if not result:
        return False, f"No matching records found for '{tool_name}'."
        
    if isinstance(result, dict) and "error" in result:
        return False, result["error"]
        
    if isinstance(result, list) and len(result) == 0:
        return False, f"Empty list returned by '{tool_name}'."

    return True, ""


def recover_company_name(failed_name: str) -> Optional[str]:
    """Recover and suggest correct company names by performing fuzzy matching on repositories."""
    try:
        container = get_container()
        companies = container.company_repo.load_all()
    except Exception:
        return None

    # Try exact lowercase substring match
    matches = [c.name for c in companies if failed_name.lower() in c.name.lower()]
    if matches:
        return matches[0]

    # Try character-based fuzzy matching
    from difflib import get_close_matches
    all_names = [c.name for c in companies]
    close = get_close_matches(failed_name, all_names, n=1, cutoff=0.5)
    if close:
        return close[0]

    return None
