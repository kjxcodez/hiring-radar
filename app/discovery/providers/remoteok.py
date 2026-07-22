"""RemoteOK provider adapter for the async discovery engine.

Wraps the existing synchronous ``app.discover.remoteok.discover`` function
in a ``DiscoveryProvider`` that the coordinator can await concurrently.

RemoteOK is a feed-based source — it takes a ``limit`` count rather than
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


@ProviderRegistry.register("remoteok")
class RemoteOKProvider(DiscoveryProvider):
    """Async adapter for the RemoteOK global job feed."""

    name = "remoteok"
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
        from app.discover.remoteok import discover as _sync_discover

        loop = asyncio.get_event_loop()
        try:
            # Feed-based: ignore slugs, use limit directly
            fn = functools.partial(_sync_discover, limit=limit)
            companies = await loop.run_in_executor(None, fn)
            logger.info(
                "remoteok: async discover complete — {n} companies",
                n=len(companies),
            )
            return companies
        except Exception as exc:  # noqa: BLE001
            logger.warning("remoteok: async discover failed — {exc}", exc=exc)
            return []
