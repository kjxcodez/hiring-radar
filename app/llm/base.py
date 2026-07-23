"""Abstract base provider class for LLMs integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from app.llm.models import LLMRequest, LLMResponse, StreamingChunk, ProviderCapabilities


class BaseLLMProvider(ABC):
    """Abstract base class representing an LLM backend API client."""

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute a standard chat completion request."""
        pass

    @abstractmethod
    def stream(self, request: LLMRequest) -> Iterator[StreamingChunk]:
        """Execute a streaming chat completion request."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Perform a connection or credentials health check."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Return the capabilities catalog of this provider."""
        pass
