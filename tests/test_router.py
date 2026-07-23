"""Tests for LLM Routing Layer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from app.llm.models import LLMRequest, LLMResponse, UsageStatistics
from app.llm.router import LLMRouter


def test_router_complete_successful() -> None:
    """Verify router successfully calls configured provider client."""
    req = LLMRequest(
        messages=[{"role": "user", "content": "hi"}],
        task_type="planner"
    )
    
    mock_res = LLMResponse(
        content="Grounded answer",
        provider="google",
        model="gemini-2.5-flash",
        usage=UsageStatistics(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    )
    
    with patch("app.llm.router.get_provider") as mock_get:
        mock_client = MagicMock()
        mock_client.is_healthy.return_value = True
        mock_client.complete.return_value = mock_res
        mock_get.return_value = mock_client
        
        from app.llm.cache import global_llm_cache
        global_llm_cache.clear()
        
        res = LLMRouter.complete(req)
        assert res.content == "Grounded answer"
        assert res.provider == "google"
        assert res.model == "gemini-2.5-flash"
