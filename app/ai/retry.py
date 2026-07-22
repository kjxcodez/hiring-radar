"""Centralized retry policy for AI Gateway requests."""

from __future__ import annotations

from typing import Any, Callable

import httpx
from loguru import logger
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)


def is_transient_error(exc: BaseException) -> bool:
    """Check if the exception is a transient network error or rate limit."""
    if isinstance(exc, httpx.HTTPStatusError):
        # 429: Too Many Requests, 5xx: Server errors
        return exc.response.status_code in (429, 502, 503, 504)
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False


def get_retry_decorator() -> Callable[[Any], Any]:
    """Return a configured tenacity retry decorator for transient errors."""
    return retry(
        retry=retry_if_exception(is_transient_error),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
