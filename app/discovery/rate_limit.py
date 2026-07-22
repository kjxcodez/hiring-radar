"""Async rate limiter for the discovery coordinator.

Provides per-provider concurrency control (via ``asyncio.Semaphore``) and
optional RPS throttling (via ``asyncio.sleep``).

Usage::

    limiter = AsyncRateLimiter(max_concurrent=5, rps=2.0)

    async with limiter:
        result = await fetch_something()
"""

from __future__ import annotations

import asyncio
import time
from typing import Any


class AsyncRateLimiter:
    """Async-safe per-provider rate limiter.

    Combines:
    - A ``asyncio.Semaphore`` to cap the maximum number of simultaneous
      in-flight requests for this provider.
    - A minimum inter-request delay derived from *rps* (requests per second)
      to avoid hammering the upstream API.

    The limiter is designed to be used as an async context manager::

        limiter = AsyncRateLimiter(max_concurrent=8, rps=3.0)

        async with limiter:
            response = await client.get(url)

    Args:
        max_concurrent: Maximum simultaneous requests allowed at once.
        rps: Target request rate in requests per second.  Set to ``0`` to
            disable RPS throttling (semaphore-only mode).
    """

    def __init__(self, max_concurrent: int = 5, rps: float = 2.0) -> None:
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent))
        self._min_interval: float = (1.0 / rps) if rps > 0 else 0.0
        self._last_release: float = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "AsyncRateLimiter":
        await self._semaphore.acquire()
        if self._min_interval > 0:
            async with self._lock:
                now = time.monotonic()
                wait = self._min_interval - (now - self._last_release)
                if wait > 0:
                    await asyncio.sleep(wait)
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._min_interval > 0:
            async with self._lock:
                self._last_release = time.monotonic()
        self._semaphore.release()

    async def acquire(self) -> None:
        """Acquire the rate limiter (alternative to context manager)."""
        await self.__aenter__()

    def release(self) -> None:
        """Release the rate limiter (alternative to context manager)."""
        self._semaphore.release()
        if self._min_interval > 0:
            self._last_release = time.monotonic()


# ---------------------------------------------------------------------------
# Per-provider default configurations
# ---------------------------------------------------------------------------

#: Default rate-limit settings keyed by provider name.
#: Coordinators use these when no explicit override is provided.
PROVIDER_RATE_LIMITS: dict[str, dict[str, float]] = {
    "greenhouse":   {"max_concurrent": 10, "rps": 3.0},
    "lever":        {"max_concurrent": 8,  "rps": 3.0},
    "ashby":        {"max_concurrent": 8,  "rps": 2.0},
    "workable":     {"max_concurrent": 5,  "rps": 2.0},
    "bamboohr":     {"max_concurrent": 5,  "rps": 2.0},
    "remoteok":     {"max_concurrent": 1,  "rps": 0.5},
    "wwr":          {"max_concurrent": 1,  "rps": 0.5},
}


def build_limiter(provider_name: str) -> AsyncRateLimiter:
    """Build an ``AsyncRateLimiter`` using the default config for *provider_name*.

    Falls back to conservative defaults (3 concurrent, 1 rps) for unknown
    providers.
    """
    cfg = PROVIDER_RATE_LIMITS.get(provider_name, {"max_concurrent": 3, "rps": 1.0})
    return AsyncRateLimiter(
        max_concurrent=int(cfg["max_concurrent"]),
        rps=float(cfg["rps"]),
    )
