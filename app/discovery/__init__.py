"""async discovery engine — public package API.

Importing this package triggers provider self-registrations and exposes
the primary entry points for the discovery layer.

Usage::

    from app.discovery import DiscoveryCoordinator, ProviderRegistry

    coordinator = DiscoveryCoordinator(settings=settings)
    companies = coordinator.discover(
        sources=["greenhouse", "lever"],
        slugs_by_source={"greenhouse": ["stripe"], "lever": ["notion"]},
        limit=50,
    )
"""

from __future__ import annotations

from app.discovery.coordinator import DiscoveryCoordinator
from app.discovery.registry import ProviderRegistry
from app.discovery.provider import DiscoveryProvider
from app.discovery.deduplication import Deduplicator
from app.discovery.normalization import CompanyNormalizer, infer_remote_type
from app.discovery.filters import DiscoveryFilter
from app.discovery.errors import (
    DiscoveryError,
    ProviderError,
    ProviderNotFoundError,
    RateLimitExceeded,
    PaginationError,
)

__all__ = [
    "DiscoveryCoordinator",
    "ProviderRegistry",
    "DiscoveryProvider",
    "Deduplicator",
    "CompanyNormalizer",
    "infer_remote_type",
    "DiscoveryFilter",
    "DiscoveryError",
    "ProviderError",
    "ProviderNotFoundError",
    "RateLimitExceeded",
    "PaginationError",
]
