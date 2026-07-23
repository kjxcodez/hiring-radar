"""Groq LLM provider implementation."""

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


class GroqProvider(BaseLLMProvider):
    """Client for Groq API completions."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not settings.groq_api_key:
            return LLMResponse(provider="groq", model="llama-3.3-70b-versatile", content="Error: Groq key not set.")

        model_name = request.model or "llama-3.3-70b-versatile"
        
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        
        json_body = {
            "model": model_name,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        try:
            with get_http_client() as client:
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=json_body,
                    timeout=60.0
                )
                resp.raise_for_status()
                res = resp.json()

            choices = res.get("choices", [])
            content = None
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content")

            usage_info = res.get("usage", {})
            stats = UsageStatistics(
                prompt_tokens=usage_info.get("prompt_tokens", 0),
                completion_tokens=usage_info.get("completion_tokens", 0),
                total_tokens=usage_info.get("total_tokens", 0)
            )

            return LLMResponse(
                content=content,
                usage=stats,
                provider="groq",
                model=model_name
            )
        except Exception as exc:
            logger.exception("Groq completion failed")
            return LLMResponse(provider="groq", model=model_name, content=f"Error: {exc}")

    def stream(self, request: LLMRequest) -> Iterator[StreamingChunk]:
        res = self.complete(request)
        yield StreamingChunk(content=res.content, is_final=True)

    def is_healthy(self) -> bool:
        return bool(settings.groq_api_key)

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supported_models=["llama-3.3-70b-versatile", "mixtral-8x7b-32768"])
