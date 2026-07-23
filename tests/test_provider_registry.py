"""Tests for Provider Registry."""

from __future__ import annotations

from app.llm.registry import PROVIDER_REGISTRY, get_provider
from app.llm.providers.google import GoogleProvider
from app.llm.providers.openrouter import OpenRouterProvider


def test_provider_registration() -> None:
    """Verify standard providers are loaded and registered on startup."""
    assert "google" in PROVIDER_REGISTRY
    assert "openrouter" in PROVIDER_REGISTRY
    
    g_prov = get_provider("google")
    assert isinstance(g_prov, GoogleProvider)
    
    or_prov = get_provider("openrouter")
    assert isinstance(or_prov, OpenRouterProvider)
