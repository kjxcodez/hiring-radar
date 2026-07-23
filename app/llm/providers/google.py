"""Google Gemini LLM provider implementation."""

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


class GoogleProvider(BaseLLMProvider):
    """Client for Google Gemini API completions."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        api_key = settings.google_api_key
        if not api_key:
            # Fallback to check if openrouter is set
            return LLMResponse(provider="google", model="gemini-2.5-flash", content="Error: Google API key not set.")

        # Default model
        model_name = request.model or "gemini-2.5-flash"
        
        headers = {
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
                # Use standard Google OpenAI compatibility endpoint
                url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions?key={api_key}"
                resp = client.post(
                    url,
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
                provider="google",
                model=model_name
            )
        except Exception as exc:
            logger.warning("Google Gemini OpenAI compatibility endpoint failed: %s. Trying raw model endpoint.", exc)
            # Fallback to direct Gemini v1beta endpoint if OpenAI compatibility is not fully rolled out
            try:
                # Format messages to Gemini candidate format
                gemini_contents = []
                for msg in request.messages:
                    role = "user" if msg.get("role") in ("user", "system") else "model"
                    gemini_contents.append({
                        "role": role,
                        "parts": [{"text": msg.get("content", "")}]
                    })
                
                raw_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                raw_body = {
                    "contents": gemini_contents,
                    "generationConfig": {
                        "temperature": request.temperature,
                        "maxOutputTokens": request.max_tokens,
                    }
                }
                with get_http_client() as client:
                    resp = client.post(raw_url, headers={"Content-Type": "application/json"}, json=raw_body, timeout=60.0)
                    resp.raise_for_status()
                    res = resp.json()
                
                candidates = res.get("candidates", [])
                text_content = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text_content = parts[0].get("text", "")
                
                return LLMResponse(
                    content=text_content,
                    provider="google",
                    model=model_name
                )
            except Exception as raw_exc:
                logger.exception("Google Gemini raw endpoint failed")
                return LLMResponse(provider="google", model=model_name, content=f"Error: {raw_exc}")

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
        return bool(settings.google_api_key)

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supported_models=["gemini-2.5-flash", "gemini-2.5-pro"])
