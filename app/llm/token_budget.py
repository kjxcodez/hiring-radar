"""Token budget estimator for pre-flight payload checks."""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from app.llm.models import TokenEstimate

logger = logging.getLogger(__name__)


def estimate_tokens_from_text(text: str) -> int:
    """Approximate token count based on typical character length ratio (4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_request_tokens(messages: List[Dict[str, Any]], tools: Any = None) -> TokenEstimate:
    """Calculate total estimated token weight of a prompt request."""
    prompt_text = ""
    for msg in messages:
        prompt_text += msg.get("content") or ""
        
    prompt_tokens = estimate_tokens_from_text(prompt_text)
    
    # Add flat overhead for tools schemas if present
    if tools:
        prompt_tokens += 500
        
    completion_tokens = 1000
    
    return TokenEstimate(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens
    )
