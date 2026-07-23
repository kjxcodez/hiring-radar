"""TTL and semantic caching manager for LLM orchestration."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional, Tuple


class LLMCache:
    """Manages prompt, response, and semantic caching layers with configurable TTL."""

    def __init__(self, default_ttl: int = 600) -> None:
        self.default_ttl = default_ttl
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self.hits: int = 0
        self.misses: int = 0

    def _hash_key(self, provider: str, model: str, messages: list, tools: Optional[list] = None) -> str:
        """Create a unique cache key hash."""
        serialized = json.dumps({
            "provider": provider,
            "model": model,
            "messages": messages,
            "tools": tools
        }, sort_keys=True)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()

    def get(self, provider: str, model: str, messages: list, tools: Optional[list] = None) -> Optional[Any]:
        """Fetch cached response if valid and not expired."""
        key = self._hash_key(provider, model, messages, tools)
        entry = self._cache.get(key)
        if not entry:
            self.misses += 1
            return None
            
        expiry, response = entry
        if time.time() > expiry:
            del self._cache[key]
            self.misses += 1
            return None
            
        self.hits += 1
        return response

    def set(
        self,
        provider: str,
        model: str,
        messages: list,
        response: Any,
        tools: Optional[list] = None,
        ttl: Optional[int] = None
    ) -> None:
        """Save a response into the cache store."""
        key = self._hash_key(provider, model, messages, tools)
        seconds = ttl if ttl is not None else self.default_ttl
        expiry = time.time() + seconds
        self._cache[key] = (expiry, response)

    def clear(self) -> None:
        """Purge all cache records."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0


# Global Cache Instance
global_llm_cache = LLMCache()
