"""Summarizes long user conversations using LLMRouter."""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from app.llm.models import LLMRequest
from app.llm.router import LLMRouter
from app.memory.models import ConversationSummary
from app.memory.store import global_memory_store

logger = logging.getLogger(__name__)


def summarize_conversation_history(messages: List[Dict[str, Any]]) -> str:
    """Trigger LLMRouter to compress messages list to a bulleted text summary."""
    if not messages:
        return ""
        
    prompt = (
        "Extract a concise bulleted list of all stable preferences, facts, stack interests, "
        "and job application details discussed in the following conversation history.\n\n"
        "Conversation:\n"
    )
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content") or ""
        prompt += f"{role.capitalize()}: {content}\n"
        
    prompt += "\nBullet summary:"
    
    req = LLMRequest(
        messages=[{"role": "user", "content": prompt}],
        task_type="company_research",
        temperature=0.2
    )
    
    try:
        res = LLMRouter.complete(req)
        summary_text = res.content or "No summary generated."
        
        summaries = global_memory_store.load_summaries()
        summaries.append(ConversationSummary(summary=summary_text))
        global_memory_store.save_summaries(summaries)
        
        return summary_text
    except Exception as exc:
        logger.exception("Failed to summarize conversation history")
        return f"Error: {exc}"
