from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel

from app.config import Settings
from app.ai.cache import AiCache
from app.ai.gateway import AiGateway, clean_json_content
from app.ai.models import FAST_MODEL, resolve_model_name
from app.ai.prompts import get_prompt, SYSTEM_PROMPTS


class DummySchema(BaseModel):
    name: str
    score: int


def test_clean_json_content():
    raw = "```json\n{\n  \"name\": \"test\"\n}\n```"
    assert clean_json_content(raw) == "{\n  \"name\": \"test\"\n}"


def test_prompt_registry():
    prompt_def = get_prompt("enrichment.v1")
    assert prompt_def.identifier == "enrichment"
    assert prompt_def.version == "v1"
    assert "professional cold outreach" in prompt_def.system_prompt_template

    with pytest.raises(KeyError):
        get_prompt("non_existent_prompt")


def test_resolve_model_name():
    settings = Settings()
    settings.openrouter_model = "google/gemini-flash"

    resolved = resolve_model_name(FAST_MODEL, settings)
    assert resolved == "google/gemini-flash"

    resolved_custom = resolve_model_name("openai/gpt-4o", settings)
    assert resolved_custom == "openai/gpt-4o"


def test_ai_cache_disabled_by_default(tmp_path: Path):
    cache_path = tmp_path / "cache.json"
    cache = AiCache(cache_path)
    assert not cache.is_enabled

    cache.set("prompt", "model", 0.4, "result")
    assert not cache_path.exists()
    assert cache.get("prompt", "model", 0.4) is None


def test_ai_cache_hits_and_misses(tmp_path: Path):
    cache_path = tmp_path / "cache.json"
    cache = AiCache(cache_path)
    cache.enable()

    assert cache.is_enabled
    assert cache.get("hello", "model", 0.3) is None

    cache.set("hello", "model", 0.3, "world")
    assert cache_path.exists()
    assert cache.get("hello", "model", 0.3) == "world"


@patch("app.ai.gateway.OpenRouterClient")
def test_gateway_complete_routing(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "output text",
                }
            }
        ]
    }
    mock_client.generate.return_value = mock_response
    mock_client_cls.return_value = mock_client

    settings = Settings()
    settings.openrouter_api_key = "mock-key"
    settings.openrouter_model = "fast-model"

    gateway = AiGateway(settings)
    res = gateway.complete(
        prompt_id="enrichment.v1",
        user_content="some content",
        model=FAST_MODEL,
        temperature=0.4,
    )

    assert res == "output text"
    mock_client.generate.assert_called_once()
    args, kwargs = mock_client.generate.call_args
    assert kwargs["model"] == "fast-model"
    assert kwargs["temperature"] == 0.4


@patch("app.ai.gateway.OpenRouterClient")
def test_gateway_complete_json_validation(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "{\n  \"name\": \"Alice\",\n  \"score\": 95\n}",
                }
            }
        ]
    }
    mock_client.generate.return_value = mock_response
    mock_client_cls.return_value = mock_client

    settings = Settings()
    settings.openrouter_api_key = "mock-key"

    gateway = AiGateway(settings)
    parsed = gateway.complete_json(
        prompt_id="enrichment.v1",
        user_content="data",
        response_model=DummySchema,
    )

    assert isinstance(parsed, DummySchema)
    assert parsed.name == "Alice"
    assert parsed.score == 95


@patch("app.ai.gateway.OpenRouterClient")
def test_gateway_retry_on_transient_failure(mock_client_cls):
    mock_client = MagicMock()
    # Fail first with a 429 status error, then succeed
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    error_429 = httpx.HTTPStatusError(
        "Too Many Requests",
        request=MagicMock(),
        response=mock_resp_429,
    )

    mock_resp_ok = MagicMock()
    mock_resp_ok.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "recovered",
                }
            }
        ]
    }

    mock_client.generate.side_effect = [error_429, mock_resp_ok]
    mock_client_cls.return_value = mock_client

    settings = Settings()
    settings.openrouter_api_key = "mock-key"

    gateway = AiGateway(settings)

    # Patch the wait time so tests run instantly
    with patch("tenacity.nap.time.sleep", return_value=None):
        res = gateway.complete(
            prompt_id="enrichment.v1",
            user_content="retry test",
        )

    assert res == "recovered"
    assert mock_client.generate.call_count == 2
