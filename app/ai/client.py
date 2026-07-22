"""Provider client for communicating with OpenRouter API."""

from __future__ import annotations

import httpx


class OpenRouterClient:
    """Executes completions requests against OpenRouter endpoints."""

    def __init__(
        self,
        api_key: str,
        referer: str = "https://github.com/kjxcodez/hiring-radar",
        app_title: str = "hiring-radar",
    ):
        self.api_key = api_key
        self.referer = referer
        self.app_title = app_title
        self._url = "https://openrouter.ai/api/v1/chat/completions"

    def generate(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        tools: list[dict] | None = None,
    ) -> httpx.Response:
        """Perform HTTP POST request to OpenRouter chat completion API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.referer,
            "X-Title": self.app_title,
        }
        json_body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            json_body["tools"] = tools

        from app.utils import get_http_client
        with get_http_client() as client:
            resp = client.post(self._url, headers=headers, json=json_body, timeout=60.0)
            resp.raise_for_status()
            return resp
