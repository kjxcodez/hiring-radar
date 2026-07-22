"""Ashby provider adapter for the async discovery engine.

Wraps the existing synchronous ``app.discover.ashby.discover`` function
in a ``DiscoveryProvider`` that the coordinator can await concurrently.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.discovery.provider import DiscoveryProvider
from app.discovery.registry import ProviderRegistry
from app.models import Company


@ProviderRegistry.register("ashby")
class AshbyProvider(DiscoveryProvider):
    """Async adapter for the Ashby public job-board API."""

    name = "ashby"
    default_concurrency = 8
    default_rate_limit_rps = 2.0

    async def discover(
        self,
        slugs: list[str],
        limit: int,
        **kwargs: Any,
    ) -> list[Company]:
        if not slugs:
            logger.info("ashby: no slugs provided — skipping")
            return []

        from app.discover.ashby import discover as _sync_discover

        loop = asyncio.get_event_loop()
        try:
            companies = await loop.run_in_executor(None, _sync_discover, slugs)
            logger.info(
                "ashby: async discover complete — {n} companies",
                n=len(companies),
            )
            return companies
        except Exception as exc:  # noqa: BLE001
            logger.warning("ashby: async discover failed — {exc}", exc=exc)
            return []
