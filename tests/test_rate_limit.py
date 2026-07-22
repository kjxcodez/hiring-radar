"""Tests for AsyncRateLimiter and build_limiter helper."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.discovery.rate_limit import AsyncRateLimiter, build_limiter, PROVIDER_RATE_LIMITS


class TestAsyncRateLimiter:

    def test_context_manager_acquires_and_releases(self):
        async def _run():
            limiter = AsyncRateLimiter(max_concurrent=2, rps=0)
            async with limiter:
                pass  # Should not raise
        asyncio.run(_run())

    def test_max_concurrent_respected(self):
        """At most N coroutines should be inside the limiter simultaneously."""
        max_concurrent = 3
        limiter = AsyncRateLimiter(max_concurrent=max_concurrent, rps=0)
        inside_count = 0
        max_seen = 0

        async def _task():
            nonlocal inside_count, max_seen
            async with limiter:
                inside_count += 1
                max_seen = max(max_seen, inside_count)
                await asyncio.sleep(0.01)
                inside_count -= 1

        async def _run():
            tasks = [_task() for _ in range(10)]
            await asyncio.gather(*tasks)

        asyncio.run(_run())
        assert max_seen <= max_concurrent

    def test_rps_zero_does_not_sleep(self):
        """RPS=0 disables throttling (no sleep)."""
        async def _run():
            limiter = AsyncRateLimiter(max_concurrent=5, rps=0)
            start = time.monotonic()
            for _ in range(5):
                async with limiter:
                    pass
            elapsed = time.monotonic() - start
            assert elapsed < 0.5  # Should be nearly instant

        asyncio.run(_run())

    def test_acquire_release_alternative(self):
        """Test the acquire()/release() alternative API."""
        async def _run():
            limiter = AsyncRateLimiter(max_concurrent=1, rps=0)
            await limiter.acquire()
            limiter.release()

        asyncio.run(_run())


class TestBuildLimiter:

    def test_known_provider_returns_limiter(self):
        for name in PROVIDER_RATE_LIMITS:
            limiter = build_limiter(name)
            assert isinstance(limiter, AsyncRateLimiter)

    def test_unknown_provider_uses_conservative_defaults(self):
        limiter = build_limiter("totally_unknown_xyz")
        assert isinstance(limiter, AsyncRateLimiter)

    def test_all_registered_providers_have_limits(self):
        expected = {"greenhouse", "lever", "ashby", "workable", "bamboohr", "remoteok", "wwr"}
        assert expected.issubset(set(PROVIDER_RATE_LIMITS.keys()))
