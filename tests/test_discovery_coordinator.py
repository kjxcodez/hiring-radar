"""Tests for the async DiscoveryCoordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.discovery.coordinator import DiscoveryCoordinator
from app.discovery.registry import ProviderRegistry
from app.discovery.provider import DiscoveryProvider
from app.models import Company, JobPosting


def _make_company(name: str, source: str = "test") -> Company:
    return Company(
        name=name,
        ats_platform=source,
        ats_slug=name.lower(),
        jobs=[
            JobPosting(
                job_title="Engineer",
                job_url=f"https://{name.lower()}.com/job",
                source=source,
            )
        ],
        discovered_at=datetime.now(),
        last_updated=datetime.now(),
    )


class _FastProvider(DiscoveryProvider):
    name = "fast"
    async def discover(self, slugs, limit, **kwargs):
        return [_make_company("FastCo", "fast")]


class _SlowProvider(DiscoveryProvider):
    name = "slow"
    async def discover(self, slugs, limit, **kwargs):
        await asyncio.sleep(0.01)
        return [_make_company("SlowCo", "slow")]


class _FailingProvider(DiscoveryProvider):
    name = "failing"
    async def discover(self, slugs, limit, **kwargs):
        raise RuntimeError("provider error!")


class _EmptyProvider(DiscoveryProvider):
    name = "empty"
    async def discover(self, slugs, limit, **kwargs):
        return []


@pytest.fixture(autouse=True)
def patch_registry():
    """Register test providers and restore afterward."""
    originals = dict(ProviderRegistry._providers)
    ProviderRegistry.register_class("fast", _FastProvider)
    ProviderRegistry.register_class("slow", _SlowProvider)
    ProviderRegistry.register_class("failing", _FailingProvider)
    ProviderRegistry.register_class("empty", _EmptyProvider)
    yield
    ProviderRegistry._providers = originals


class TestDiscoveryCoordinator:

    def test_single_provider_returns_companies(self):
        coordinator = DiscoveryCoordinator()
        result = coordinator.discover(
            sources=["fast"],
            slugs_by_source={"fast": ["slug1"]},
            limit=10,
        )
        assert len(result) == 1
        assert result[0].name == "FastCo"

    def test_multiple_providers_aggregated(self):
        coordinator = DiscoveryCoordinator()
        result = coordinator.discover(
            sources=["fast", "slow"],
            slugs_by_source={"fast": ["slug1"], "slow": ["slug2"]},
            limit=10,
        )
        names = {c.name for c in result}
        assert "FastCo" in names
        assert "SlowCo" in names

    def test_failing_provider_isolated(self):
        """A failing provider should not abort other providers."""
        coordinator = DiscoveryCoordinator()
        result = coordinator.discover(
            sources=["fast", "failing"],
            slugs_by_source={"fast": ["s1"], "failing": []},
            limit=10,
        )
        # FastCo should still be returned despite 'failing' raising
        assert any(c.name == "FastCo" for c in result)

    def test_empty_sources_returns_empty(self):
        coordinator = DiscoveryCoordinator()
        result = coordinator.discover(
            sources=[],
            slugs_by_source={},
            limit=10,
        )
        assert result == []

    def test_unknown_sources_skipped(self):
        coordinator = DiscoveryCoordinator()
        result = coordinator.discover(
            sources=["fast", "unknown_xyz_999"],
            slugs_by_source={"fast": ["s1"]},
            limit=10,
        )
        # Unknown source is warned about but doesn't crash; fast still runs
        assert any(c.name == "FastCo" for c in result)

    def test_progress_callback_invoked(self):
        """Progress callback is called once per completing provider."""
        called_with = []

        def _cb(src_name, companies):
            called_with.append(src_name)

        coordinator = DiscoveryCoordinator()
        coordinator.discover(
            sources=["fast", "empty"],
            slugs_by_source={"fast": [], "empty": []},
            limit=10,
            progress_callback=_cb,
        )
        assert "fast" in called_with


    def test_deduplication_across_providers(self):
        """Same company (identified by domain) from two providers should be merged.

        When two providers return the same company without ATS-specific keys,
        deduplication falls through to the domain key which is shared.
        """

        def _shared_company(source: str) -> Company:
            """Both providers return SharedCo with the same domain.
            No ats_platform/slug is set so the domain key fires.
            """
            return Company(
                name="SharedCo",
                domain="sharedco.com",  # same domain → same dedup key
                # No ats_platform/ats_slug — dedup uses domain key
                jobs=[
                    JobPosting(
                        job_title="Engineer",
                        job_url=f"https://sharedco.com/job-{source}",
                        source=source,
                    )
                ],
                discovered_at=datetime.now(),
                last_updated=datetime.now(),
            )

        class _Dup1Provider(DiscoveryProvider):
            name = "dup1"
            async def discover(self, slugs, limit, **kwargs):
                return [_shared_company("dup1")]

        class _Dup2Provider(DiscoveryProvider):
            name = "dup2"
            async def discover(self, slugs, limit, **kwargs):
                return [_shared_company("dup2")]

        ProviderRegistry.register_class("dup1", _Dup1Provider)
        ProviderRegistry.register_class("dup2", _Dup2Provider)

        coordinator = DiscoveryCoordinator()
        result = coordinator.discover(
            sources=["dup1", "dup2"],
            slugs_by_source={"dup1": [], "dup2": []},
            limit=20,
        )
        # domain key = "sharedco.com" for both → merged into 1 company
        sharedco = [c for c in result if c.name == "SharedCo"]
        assert len(sharedco) == 1
        # Both jobs should have been merged in
        assert len(sharedco[0].jobs) == 2

