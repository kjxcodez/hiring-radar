"""Greenhouse provider adapter for the async discovery engine.

Wraps the existing synchronous ``app.discover.greenhouse.discover`` function
in a ``DiscoveryProvider`` that the coordinator can await concurrently.
The underlying HTTP + parsing logic remains in ``app/discover/greenhouse.py``
without modification.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.discovery.provider import DiscoveryProvider
from app.discovery.registry import ProviderRegistry
from app.models import Company


@ProviderRegistry.register("greenhouse")
class GreenhouseProvider(DiscoveryProvider):
    """Async adapter for the Greenhouse public board API.

    Runs ``app.discover.greenhouse.discover`` in a thread-pool executor so
    it does not block the asyncio event loop while performing synchronous
    HTTP requests.
    """

    name = "greenhouse"
    default_concurrency = 10
    default_rate_limit_rps = 3.0

    async def discover(
        self,
        slugs: list[str],
        limit: int,
        **kwargs: Any,
    ) -> list[Company]:
        if not slugs:
            logger.info("greenhouse: no slugs provided — skipping")
            return []

        from app.discover.greenhouse import discover as _sync_discover

        loop = asyncio.get_event_loop()
        try:
            companies = await loop.run_in_executor(None, _sync_discover, slugs)
            logger.info(
                "greenhouse: async discover complete — {n} companies",
                n=len(companies),
            )
            return companies
        except Exception as exc:  # noqa: BLE001
            logger.warning("greenhouse: async discover failed — {exc}", exc=exc)
            return []
