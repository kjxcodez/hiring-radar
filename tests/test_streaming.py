"""Tests for response streaming UI helpers."""

from __future__ import annotations

from unittest.mock import patch
from app.llm.models import LLMRequest, LLMResponse, UsageStatistics
from app.llm.router import LLMRouter


def test_llm_router_stream_words() -> None:
    """Verify stream splits text into words correctly."""
    req = LLMRequest(messages=[{"role": "user", "content": "hi"}])
    
    mock_res = LLMResponse(
        content="This is a test response",
        provider="google",
        model="gemini-2.5-flash",
        usage=UsageStatistics(prompt_tokens=5, completion_tokens=5, total_tokens=10)
    )
    
    with patch("app.llm.router.LLMRouter.complete") as mock_complete:
        mock_complete.return_value = mock_res
        
        chunks = list(LLMRouter.stream(req))
        assert len(chunks) == 5
        assert "".join(c.content for c in chunks) == "This is a test response"
        assert chunks[-1].is_final is True
