"""Abstract base class for all discovery providers.

Every ATS or job-board integration must subclass ``DiscoveryProvider`` and
implement ``discover()``.  The coordinator calls providers through this
interface, enabling uniform concurrency, rate-limiting, and error handling
regardless of the underlying API shape.

Usage::

    from app.discovery.provider import DiscoveryProvider

    class MyATSProvider(DiscoveryProvider):
        name = "myats"

        async def discover(self, slugs, limit, **kwargs):
            ...
            return companies
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models import Company


class DiscoveryProvider(ABC):
    """Interface every ATS/job-board discovery adapter must implement.

    Providers are instantiated once per coordinator run.  They should be
    stateless — all per-request state lives in local variables.
    """

    #: Short machine-readable name, e.g. ``"greenhouse"``.  Must be unique
    #: across all registered providers.
    name: str = "unnamed"

    #: Maximum number of slugs to fetch concurrently within this provider.
    #: Slug-based providers (Greenhouse, Lever, …) use this to cap the
    #: asyncio task fan-out.  Feed-based providers (RemoteOK, WWR) ignore it.
    default_concurrency: int = 5

    #: Desired request rate in requests per second for this provider.
    #: Used by ``AsyncRateLimiter`` to pace slug-level fetches.
    default_rate_limit_rps: float = 2.0

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def discover(
        self,
        slugs: list[str],
        limit: int,
        **kwargs: Any,
    ) -> list[Company]:
        """Fetch companies from this provider.

        Args:
            slugs:  List of company slugs/tokens for slug-based providers.
                    Empty for feed-based providers (``is_feed_based()`` is
                    ``True``).
            limit:  Maximum number of jobs or companies to return.
                    Providers should respect this to avoid over-fetching.
            **kwargs: Extra context forwarded from the coordinator (e.g.
                    ``remote``, ``country``).

        Returns:
            A (possibly empty) list of :class:`~app.models.Company` objects.
            Must never raise — catch all exceptions internally and return
            ``[]`` with a ``logger.warning``.
        """

    # ------------------------------------------------------------------
    # Capability flags (override in subclasses as needed)
    # ------------------------------------------------------------------

    def is_feed_based(self) -> bool:
        """Return ``True`` for global-feed providers that don't take slugs.

        Feed-based providers (RemoteOK, WWR) receive ``slugs=[]`` and use
        ``limit`` to cap collection instead.
        """
        return False

    def supports_remote_flag(self) -> bool:
        """Return ``True`` if this provider can natively filter by remote."""
        return False

    def supports_pagination(self) -> bool:
        """Return ``True`` if the provider implements multi-page fetching."""
        return False

    def supports_country_filter(self) -> bool:
        """Return ``True`` if the provider API accepts a country parameter."""
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
