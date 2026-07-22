"""Model identifiers and resolution mapping for Hiring Radar."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings

FAST_MODEL = "fast"
QUALITY_MODEL = "quality"
REASONING_MODEL = "reasoning"


def resolve_model_name(model_alias: str, settings: Settings) -> str:
    """Resolve an abstract model name to the concrete OpenRouter model string."""
    if model_alias == FAST_MODEL:
        return settings.openrouter_model or "openrouter/free"
    elif model_alias == QUALITY_MODEL:
        return getattr(settings, "openrouter_quality_model", None) or settings.openrouter_model or "openrouter/free"
    elif model_alias == REASONING_MODEL:
        return getattr(settings, "openrouter_reasoning_model", None) or settings.openrouter_model or "openrouter/free"

    # If it's already a concrete model name, return it directly
    return model_alias
