"""OpenAI LLM provider implementation."""

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


class OpenAIProvider(BaseLLMProvider):
    """Client for OpenAI API completions."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not settings.openai_api_key:
            return LLMResponse(provider="openai", model="gpt-4o", content="Error: OpenAI key not set.")

        model_name = request.model or "gpt-4o"
        
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        
        json_body = {
            "model": model_name,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            json_body["tools"] = request.tools

        try:
            with get_http_client() as client:
                resp = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=json_body,
                    timeout=60.0
                )
                resp.raise_for_status()
                res = resp.json()

            choices = res.get("choices", [])
            content = None
            tool_calls = None
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content")
                tool_calls = msg.get("tool_calls")

            usage_info = res.get("usage", {})
            stats = UsageStatistics(
                prompt_tokens=usage_info.get("prompt_tokens", 0),
                completion_tokens=usage_info.get("completion_tokens", 0),
                total_tokens=usage_info.get("total_tokens", 0)
            )

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                usage=stats,
                provider="openai",
                model=model_name
            )
        except Exception as exc:
            logger.exception("OpenAI completion failed")
            return LLMResponse(provider="openai", model=model_name, content=f"Error: {exc}")

    def stream(self, request: LLMRequest) -> Iterator[StreamingChunk]:
        res = self.complete(request)
        if not res.content:
            yield StreamingChunk(content=None, tool_calls=res.tool_calls, is_final=True)
            return
        words = res.content.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield StreamingChunk(content=chunk, is_final=(i == len(words) - 1))

    def is_healthy(self) -> bool:
        return bool(settings.openai_api_key)

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supported_models=["gpt-4o", "gpt-4o-mini", "gpt-5"])
