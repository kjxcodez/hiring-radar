"""Provider registry for the async discovery engine.

Maps provider name strings to ``DiscoveryProvider`` subclasses.  Providers
self-register at import time using the ``@ProviderRegistry.register``
decorator so no manual wiring is required when adding a new provider.

Usage::

    # In a provider module:
    @ProviderRegistry.register("greenhouse")
    class GreenhouseProvider(DiscoveryProvider):
        ...

    # In the coordinator:
    provider = ProviderRegistry.get("greenhouse")
    companies = await provider.discover(slugs, limit)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.discovery.errors import ProviderNotFoundError

if TYPE_CHECKING:
    from app.discovery.provider import DiscoveryProvider


class ProviderRegistry:
    """Central registry mapping provider names to their implementation classes.

    All methods are class-level so a single shared registry is used across
    the entire process without needing to pass an instance around.
    """

    _providers: dict[str, type["DiscoveryProvider"]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    @classmethod
    def register(cls, name: str):
        """Class decorator that registers a provider under *name*.

        Example::

            @ProviderRegistry.register("lever")
            class LeverProvider(DiscoveryProvider):
                ...
        """
        def decorator(provider_cls: type["DiscoveryProvider"]) -> type["DiscoveryProvider"]:
            cls._providers[name] = provider_cls
            return provider_cls
        return decorator

    @classmethod
    def register_class(cls, name: str, provider_cls: type["DiscoveryProvider"]) -> None:
        """Explicitly register *provider_cls* under *name* (non-decorator form)."""
        cls._providers[name] = provider_cls

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    @classmethod
    def get(cls, name: str) -> "DiscoveryProvider":
        """Instantiate and return the provider registered under *name*.

        Args:
            name: Provider identifier, e.g. ``"greenhouse"``.

        Returns:
            A fresh ``DiscoveryProvider`` instance.

        Raises:
            ProviderNotFoundError: If no provider is registered for *name*.
        """
        provider_cls = cls._providers.get(name)
        if provider_cls is None:
            raise ProviderNotFoundError(name)
        return provider_cls()

    @classmethod
    def has(cls, name: str) -> bool:
        """Return ``True`` if a provider is registered under *name*."""
        return name in cls._providers

    @classmethod
    def all_names(cls) -> list[str]:
        """Return a sorted list of all registered provider names."""
        return sorted(cls._providers.keys())

    @classmethod
    def all_providers(cls) -> dict[str, type["DiscoveryProvider"]]:
        """Return a copy of the internal registry dict."""
        return dict(cls._providers)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered providers.  Primarily useful in tests."""
        cls._providers.clear()
