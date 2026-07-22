"""We Work Remotely provider adapter for the async discovery engine.

Wraps the existing synchronous ``app.discover.wwr.discover`` function
in a ``DiscoveryProvider`` that the coordinator can await concurrently.

WWR is a feed-based source — it takes a ``limit`` count rather than
a slug list.  ``is_feed_based()`` returns ``True`` so the coordinator
passes ``slugs=[]`` and routes the ``limit`` argument correctly.
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any

from loguru import logger

from app.discovery.provider import DiscoveryProvider
from app.discovery.registry import ProviderRegistry
from app.models import Company


@ProviderRegistry.register("wwr")
class WWRProvider(DiscoveryProvider):
    """Async adapter for the We Work Remotely RSS feed."""

    name = "wwr"
    default_concurrency = 1
    default_rate_limit_rps = 0.5

    def is_feed_based(self) -> bool:
        return True

    async def discover(
        self,
        slugs: list[str],
        limit: int,
        **kwargs: Any,
    ) -> list[Company]:
        from app.discover.wwr import discover as _sync_discover

        loop = asyncio.get_event_loop()
        try:
            fn = functools.partial(_sync_discover, limit=limit)
            companies = await loop.run_in_executor(None, fn)
            logger.info(
                "wwr: async discover complete — {n} companies",
                n=len(companies),
            )
            return companies
        except Exception as exc:  # noqa: BLE001
            logger.warning("wwr: async discover failed — {exc}", exc=exc)
            return []
