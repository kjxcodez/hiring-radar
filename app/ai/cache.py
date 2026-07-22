"""Transparent caching for AI responses to prevent duplicate network calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.storage import JsonStorage


class AiCache:
    """Intelligent cached results manager using atomic JSON storage."""

    def __init__(self, cache_file: Path = Path("output/ai_cache.json")):
        self.cache_file = cache_file
        self.storage = JsonStorage()
        self._enabled = False

    def enable(self) -> None:
        """Enable caching."""
        self._enabled = True

    def disable(self) -> None:
        """Disable caching."""
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled

    def _generate_key(
        self,
        prompt: str,
        model: str,
        temperature: float,
        structured_schema: str | None = None,
        provider: str = "openrouter",
    ) -> str:
        """Generate a stable SHA-256 hash representing the query parameters."""
        payload = {
            "prompt": prompt,
            "model": model,
            "temperature": temperature,
            "structured_schema": structured_schema,
            "provider": provider,
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(
        self,
        prompt: str,
        model: str,
        temperature: float,
        structured_schema: str | None = None,
        provider: str = "openrouter",
    ) -> str | None:
        """Retrieve a cached completion value, or return None if missed/disabled."""
        if not self._enabled:
            return None

        cache_data = self.storage.read(self.cache_file)
        if not cache_data or not isinstance(cache_data, dict):
            return None

        key = self._generate_key(prompt, model, temperature, structured_schema, provider)
        return cache_data.get(key)

    def set(
        self,
        prompt: str,
        model: str,
        temperature: float,
        value: str,
        structured_schema: str | None = None,
        provider: str = "openrouter",
    ) -> None:
        """Store a completion value in the cache file."""
        if not self._enabled:
            return

        cache_data = self.storage.read(self.cache_file)
        if not cache_data or not isinstance(cache_data, dict):
            cache_data = {}

        key = self._generate_key(prompt, model, temperature, structured_schema, provider)
        cache_data[key] = value

        self.storage.write(self.cache_file, cache_data)

    def clear(self) -> None:
        """Delete the cache file."""
        self.storage.delete(self.cache_file)
