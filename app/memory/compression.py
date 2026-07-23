"""Context compression and old conversation summaries triggers."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from app.memory.summarizer import summarize_conversation_history

logger = logging.getLogger(__name__)


def compress_conversation_history(messages: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Compress older conversation turns into a summarized context card once limits are exceeded."""
    if len(messages) <= limit:
        return messages

    system_msg = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    
    to_summarize = non_system[:-4]
    to_keep = non_system[-4:]
    
    if to_summarize:
        logger.info("Compressing conversation: summarizing %d messages", len(to_summarize))
        summary = summarize_conversation_history(to_summarize)
        
        summary_msg = {
            "role": "assistant",
            "content": f"[System Context Summary of previous turns]:\n{summary}"
        }
        return system_msg + [summary_msg] + to_keep
        
    return messages
