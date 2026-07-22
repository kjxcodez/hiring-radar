"""BambooHR provider adapter for the async discovery engine.

Wraps the existing synchronous ``app.discover.bamboohr.discover`` function
in a ``DiscoveryProvider`` that the coordinator can await concurrently.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.discovery.provider import DiscoveryProvider
from app.discovery.registry import ProviderRegistry
from app.models import Company


@ProviderRegistry.register("bamboohr")
class BambooHRProvider(DiscoveryProvider):
    """Async adapter for the BambooHR public careers list API."""

    name = "bamboohr"
    default_concurrency = 5
    default_rate_limit_rps = 2.0

    async def discover(
        self,
        slugs: list[str],
        limit: int,
        **kwargs: Any,
    ) -> list[Company]:
        if not slugs:
            logger.info("bamboohr: no slugs provided — skipping")
            return []

        from app.discover.bamboohr import discover as _sync_discover

        loop = asyncio.get_event_loop()
        try:
            companies = await loop.run_in_executor(None, _sync_discover, slugs)
            logger.info(
                "bamboohr: async discover complete — {n} companies",
                n=len(companies),
            )
            return companies
        except Exception as exc:  # noqa: BLE001
            logger.warning("bamboohr: async discover failed — {exc}", exc=exc)
            return []
