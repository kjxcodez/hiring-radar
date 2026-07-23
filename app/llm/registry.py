"""Provider Registry maintaining LLM class definitions."""

from __future__ import annotations

from typing import Dict, Type, Optional
from app.llm.base import BaseLLMProvider

PROVIDER_REGISTRY: Dict[str, Type[BaseLLMProvider]] = {}


def register_provider(name: str, provider_cls: Type[BaseLLMProvider]) -> None:
    """Register a new LLM provider class in the workspace catalog."""
    PROVIDER_REGISTRY[name.lower()] = provider_cls


def get_provider(name: str) -> Optional[BaseLLMProvider]:
    """Instantiate and return a registered provider client."""
    provider_cls = PROVIDER_REGISTRY.get(name.lower())
    if not provider_cls:
        return None
    return provider_cls()
