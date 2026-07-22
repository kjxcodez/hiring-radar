"""AI Gateway orchestrator coordinating model mapping, retries, caching, and validation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from app.ai.cache import AiCache
from app.ai.client import OpenRouterClient
from app.ai.models import resolve_model_name
from app.ai.prompts import get_prompt
from app.ai.retry import get_retry_decorator

if TYPE_CHECKING:
    from app.config import Settings

T = TypeVar("T", bound=BaseModel)


def clean_json_content(content: str) -> str:
    """Strip markdown code blocks or formatting fences from LLM output."""
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


class AiGateway:
    """Central entrypoint for executing all AI and LLM operations."""

    def __init__(self, settings: Settings, cache: AiCache | None = None):
        self.settings = settings
        self.cache = cache or AiCache()
        self._retry_decorator = get_retry_decorator()

    def _get_client(self) -> OpenRouterClient:
        """Create a configured OpenRouterClient instance."""
        return OpenRouterClient(
            api_key=self.settings.openrouter_api_key or "",
        )

    def complete(
        self,
        prompt_id: str | None = None,
        user_content: str | None = None,
        messages: list[dict[str, str]] | None = None,
        model: str | None = None,
        temperature: float = 0.4,
        use_cache: bool = False,
        tools: list[dict] | None = None,
        system_placeholders: dict[str, str] | None = None,
        return_raw_choice: bool = False,
    ) -> Any:
        """Execute a completion query against the LLM provider."""
        # 1. Resolve model name
        target_model = resolve_model_name(model or "fast", self.settings)

        # 2. Build or extract messages
        final_messages: list[dict[str, str]] = []
        system_prompt = ""

        if prompt_id:
            prompt_def = get_prompt(prompt_id)
            system_prompt = prompt_def.system_prompt_template
            if system_placeholders:
                system_prompt = system_prompt.format(**system_placeholders)

            final_messages.append({"role": "system", "content": system_prompt})

            if user_content:
                final_messages.append({"role": "user", "content": user_content})

        if messages:
            # If a system prompt is already loaded, prepend it if not already present in messages
            if final_messages and not any(m.get("role") == "system" for m in messages):
                final_messages.extend(messages)
            else:
                final_messages = messages

        # 3. Check Cache
        cache_key_prompt = json.dumps(final_messages, sort_keys=True)
        if use_cache and self.cache.is_enabled and not return_raw_choice:
            cached_val = self.cache.get(
                prompt=cache_key_prompt,
                model=target_model,
                temperature=temperature,
            )
            if cached_val is not None:
                return cached_val

        # Verify API Key
        if not self.settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Please add it to your .env file."
            )

        # 4. Define client completions call with retry wrapper
        client = self._get_client()

        @self._retry_decorator
        def _execute_call() -> dict[str, Any]:
            resp = client.generate(
                messages=final_messages,
                model=target_model,
                temperature=temperature,
                tools=tools,
            )
            resp_payload = resp.json()
            return resp_payload["choices"][0]["message"]

        choice_message = _execute_call()
        result = choice_message.get("content") or ""

        # 5. Write to Cache
        if use_cache and self.cache.is_enabled and not return_raw_choice:
            self.cache.set(
                prompt=cache_key_prompt,
                model=target_model,
                temperature=temperature,
                value=result,
            )

        if return_raw_choice:
            return choice_message

        return result

    def complete_json(
        self,
        prompt_id: str | None = None,
        user_content: str | None = None,
        messages: list[dict[str, str]] | None = None,
        model: str | None = None,
        temperature: float = 0.4,
        use_cache: bool = False,
        tools: list[dict] | None = None,
        system_placeholders: dict[str, str] | None = None,
        response_model: type[T] | None = None,
    ) -> T | dict[str, Any]:
        """Execute a completion query and parse/validate the output as JSON/Pydantic."""
        raw_text = self.complete(
            prompt_id=prompt_id,
            user_content=user_content,
            messages=messages,
            model=model,
            temperature=temperature,
            use_cache=use_cache,
            tools=tools,
            system_placeholders=system_placeholders,
        )

        clean_json = clean_json_content(raw_text)
        parsed = json.loads(clean_json)

        if response_model:
            return response_model.model_validate(parsed)

        return parsed
