"""Tests for Token Budgeting and Compression."""

from __future__ import annotations

from app.llm.token_budget import estimate_request_tokens
from app.llm.compression import compress_history


def test_token_estimation() -> None:
    """Verify character-ratio based token weight estimation."""
    msgs = [{"role": "user", "content": "Hello world"}]
    estimate = estimate_request_tokens(msgs)
    assert estimate.prompt_tokens == 2
    

def test_context_compression() -> None:
    """Verify history compression logic trims older messages correctly."""
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": "2"},
        {"role": "user", "content": "3"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "5"},
        {"role": "assistant", "content": "6"},
    ]
    
    compressed = compress_history(msgs, max_turns=4)
    assert len(compressed) == 5
    assert compressed[0]["content"] == "sys"
    assert compressed[1]["content"] == "3"
