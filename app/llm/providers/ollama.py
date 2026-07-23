"""Ollama local inference LLM provider implementation."""

from __future__ import annotations

import json
import logging
from typing import Iterator

import httpx
from app.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.models import LLMRequest, LLMResponse, StreamingChunk, ProviderCapabilities, UsageStatistics
from app.utils import get_http_client

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Client for local Ollama API completions."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        base_url = settings.ollama_base_url or "http://localhost:11434"
        model_name = request.model or "llama3"

        json_body = {
            "model": model_name,
            "messages": request.messages,
            "stream": False,
            "options": {
                "temperature": request.temperature
            }
        }

        try:
            with get_http_client() as client:
                url = f"{base_url.rstrip('/')}/api/chat"
                resp = client.post(
                    url,
                    json=json_body,
                    timeout=60.0
                )
                resp.raise_for_status()
                res = resp.json()

            msg = res.get("message", {})
            content = msg.get("content")

            return LLMResponse(
                content=content,
                provider="ollama",
                model=model_name
            )
        except Exception as exc:
            logger.warning("Ollama connection failed: %s", exc)
            return LLMResponse(provider="ollama", model=model_name, content=f"Error: {exc}")

    def stream(self, request: LLMRequest) -> Iterator[StreamingChunk]:
        res = self.complete(request)
        if not res.content:
            yield StreamingChunk(content=None, is_final=True)
            return
        words = res.content.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield StreamingChunk(content=chunk, is_final=(i == len(words) - 1))

    def is_healthy(self) -> bool:
        # Check if Ollama is running
        base_url = settings.ollama_base_url or "http://localhost:11434"
        try:
            with get_http_client() as client:
                resp = client.get(f"{base_url.rstrip('/')}/api/tags", timeout=2.0)
                return resp.status_code == 200
        except Exception:
            return False

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supported_models=["llama3", "mistral", "phi3"])
