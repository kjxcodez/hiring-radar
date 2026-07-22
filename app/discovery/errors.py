"""Structured exception hierarchy for the async discovery engine."""

from __future__ import annotations


class DiscoveryError(Exception):
    """Base exception for all discovery-layer errors."""


class ProviderError(DiscoveryError):
    """Raised when a provider encounters an unrecoverable error during discovery."""

    def __init__(self, provider_name: str, message: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"[{provider_name}] {message}")


class ProviderNotFoundError(DiscoveryError):
    """Raised when a requested provider name is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"No provider registered for '{name}'. "
            f"Check spelling or register the provider with ProviderRegistry."
        )


class RateLimitExceeded(DiscoveryError):
    """Raised when a rate limit cannot be satisfied within the allowed wait time."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"[{provider_name}] Rate limit exceeded — request aborted.")


class PaginationError(DiscoveryError):
    """Raised when a provider encounters a pagination inconsistency."""

    def __init__(self, provider_name: str, message: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"[{provider_name}] Pagination error: {message}")
