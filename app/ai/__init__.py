"""AI infrastructure package for Hiring Radar."""

from __future__ import annotations

from app.ai.cache import AiCache
from app.ai.gateway import AiGateway, clean_json_content
from app.ai.models import FAST_MODEL, QUALITY_MODEL, REASONING_MODEL, resolve_model_name
from app.ai.prompts import SYSTEM_PROMPTS, PromptDefinition, get_prompt

__all__ = [
    "AiGateway",
    "AiCache",
    "clean_json_content",
    "FAST_MODEL",
    "QUALITY_MODEL",
    "REASONING_MODEL",
    "resolve_model_name",
    "SYSTEM_PROMPTS",
    "PromptDefinition",
    "get_prompt",
]
