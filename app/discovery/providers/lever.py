"""Lever provider adapter for the async discovery engine.

Wraps the existing synchronous ``app.discover.lever.discover`` function
in a ``DiscoveryProvider`` that the coordinator can await concurrently.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.discovery.provider import DiscoveryProvider
from app.discovery.registry import ProviderRegistry
from app.models import Company


@ProviderRegistry.register("lever")
class LeverProvider(DiscoveryProvider):
    """Async adapter for the Lever public postings API."""

    name = "lever"
    default_concurrency = 8
    default_rate_limit_rps = 3.0

    async def discover(
        self,
        slugs: list[str],
        limit: int,
        **kwargs: Any,
    ) -> list[Company]:
        if not slugs:
            logger.info("lever: no slugs provided — skipping")
            return []

        from app.discover.lever import discover as _sync_discover

        loop = asyncio.get_event_loop()
        try:
            companies = await loop.run_in_executor(None, _sync_discover, slugs)
            logger.info(
                "lever: async discover complete — {n} companies",
                n=len(companies),
            )
            return companies
        except Exception as exc:  # noqa: BLE001
            logger.warning("lever: async discover failed — {exc}", exc=exc)
            return []
