"""Tests for ProviderRegistry — registration, lookup, and error handling."""

from __future__ import annotations

import pytest

from app.discovery.registry import ProviderRegistry
from app.discovery.provider import DiscoveryProvider
from app.discovery.errors import ProviderNotFoundError
from app.models import Company


class _DummyProvider(DiscoveryProvider):
    name = "dummy_test"

    async def discover(self, slugs, limit, **kwargs):
        return []


class TestProviderRegistry:

    def setup_method(self):
        """Clear the registry before each test to avoid pollution."""
        # Save originals
        self._originals = dict(ProviderRegistry._providers)

    def teardown_method(self):
        """Restore registry after each test."""
        ProviderRegistry._providers = self._originals

    def test_register_and_get(self):
        ProviderRegistry.register_class("dummy_test", _DummyProvider)
        provider = ProviderRegistry.get("dummy_test")
        assert isinstance(provider, _DummyProvider)

    def test_get_unknown_raises(self):
        with pytest.raises(ProviderNotFoundError) as exc_info:
            ProviderRegistry.get("nonexistent_xyz")
        assert "nonexistent_xyz" in str(exc_info.value)

    def test_has_returns_true_when_registered(self):
        ProviderRegistry.register_class("dummy_test", _DummyProvider)
        assert ProviderRegistry.has("dummy_test") is True

    def test_has_returns_false_when_not_registered(self):
        assert ProviderRegistry.has("totally_fake_source_xyz") is False

    def test_all_names_sorted(self):
        ProviderRegistry.register_class("b_source", _DummyProvider)
        ProviderRegistry.register_class("a_source", _DummyProvider)
        names = ProviderRegistry.all_names()
        assert names == sorted(names)

    def test_register_decorator(self):
        @ProviderRegistry.register("decorator_test")
        class _DecoratedProvider(DiscoveryProvider):
            name = "decorator_test"
            async def discover(self, slugs, limit, **kwargs):
                return []

        assert ProviderRegistry.has("decorator_test")
        p = ProviderRegistry.get("decorator_test")
        assert isinstance(p, _DecoratedProvider)

    def test_all_production_providers_registered(self):
        """Ensure all 7 standard providers are registered after import."""
        # Importing the package triggers registrations
        import app.discovery  # noqa: F401
        expected = {"greenhouse", "lever", "ashby", "workable", "bamboohr", "remoteok", "wwr"}
        registered = set(ProviderRegistry.all_names())
        assert expected.issubset(registered)

    def test_all_providers_returns_copy(self):
        """Modifying the returned dict doesn't affect the registry."""
        copy = ProviderRegistry.all_providers()
        copy["injected"] = _DummyProvider
        assert "injected" not in ProviderRegistry._providers
