"""Anthropic Claude LLM provider implementation."""

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


class AnthropicProvider(BaseLLMProvider):
    """Client for Anthropic Claude API completions."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not settings.anthropic_api_key:
            return LLMResponse(provider="anthropic", model="claude-3-5-sonnet", content="Error: Anthropic key not set.")

        model_name = request.model or "claude-3-5-sonnet-20241022"
        
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        # Format messages separating system instructions
        system_content = ""
        anthropic_messages = []
        for msg in request.messages:
            role = msg.get("role")
            if role == "system":
                system_content += msg.get("content", "") + "\n"
            elif role in ("user", "assistant"):
                anthropic_messages.append({
                    "role": role,
                    "content": msg.get("content", "")
                })

        json_body = {
            "model": model_name,
            "messages": anthropic_messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if system_content.strip():
            json_body["system"] = system_content.strip()

        try:
            with get_http_client() as client:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=json_body,
                    timeout=60.0
                )
                resp.raise_for_status()
                res = resp.json()

            # Parse Claude messages response content
            content_blocks = res.get("content", [])
            content_text = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    content_text += block.get("text", "")

            usage_info = res.get("usage", {})
            stats = UsageStatistics(
                prompt_tokens=usage_info.get("input_tokens", 0),
                completion_tokens=usage_info.get("output_tokens", 0),
                total_tokens=usage_info.get("input_tokens", 0) + usage_info.get("output_tokens", 0)
            )

            return LLMResponse(
                content=content_text,
                provider="anthropic",
                model=model_name,
                usage=stats
            )
        except Exception as exc:
            logger.exception("Anthropic completion failed")
            return LLMResponse(provider="anthropic", model=model_name, content=f"Error: {exc}")

    def stream(self, request: LLMRequest) -> Iterator[StreamingChunk]:
        res = self.complete(request)
        if not res.content:
            yield StreamingChunk(content=None, tool_calls=res.tool_calls, is_final=True)
            return
        words = res.content.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield StreamingChunk(chunk, is_final=(i == len(words) - 1))

    def is_healthy(self) -> bool:
        return bool(settings.anthropic_api_key)

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supported_models=["claude-3-5-sonnet", "claude-3-opus"])
