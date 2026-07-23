"""Tests for LLM Caching Layer."""

from __future__ import annotations

import time
from app.llm.cache import LLMCache


def test_cache_hits_misses_ttl() -> None:
    """Verify caching responses and TTL expiration works correctly."""
    cache = LLMCache(default_ttl=1)
    
    msgs = [{"role": "user", "content": "hi"}]
    
    val = cache.get("google", "gemini-2.5-flash", msgs)
    assert val is None
    assert cache.misses == 1
    assert cache.hits == 0
    
    cache.set("google", "gemini-2.5-flash", msgs, "Hello there!")
    
    val2 = cache.get("google", "gemini-2.5-flash", msgs)
    assert val2 == "Hello there!"
    assert cache.hits == 1
    
    time.sleep(1.1)
    
    val3 = cache.get("google", "gemini-2.5-flash", msgs)
    assert val3 is None
