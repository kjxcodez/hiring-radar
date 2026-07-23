"""Context compression and token trimming utility."""

from __future__ import annotations

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def compress_history(messages: List[Dict[str, Any]], max_turns: int = 6) -> List[Dict[str, Any]]:
    """Compress conversation messages list by preserving system prompt and trimming oldest turns."""
    if len(messages) <= max_turns + 1:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    
    trimmed = system_msgs + non_system[-max_turns:]
    logger.info("Context compressed: reduced messages from %d to %d", len(messages), len(trimmed))
    return trimmed
