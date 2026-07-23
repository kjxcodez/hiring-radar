"""Shared models and data schemas for LLM abstraction and routing."""

from __future__ import annotations

from typing import Any, Optional, Dict, List
from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    """Encapsulates parameters for a completion request."""
    messages: List[Dict[str, Any]]
    model: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 4000
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    task_type: str = "general"


class TokenEstimate(BaseModel):
    """Estimated token weight of inputs."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    is_exceeded: bool = False


class UsageStatistics(BaseModel):
    """Token consumption and financial cost stats."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    cache_hits: int = 0
    early_exits: int = 0
    latency_seconds_total: float = 0.0


class LLMResponse(BaseModel):
    """Standardized response from any LLM provider."""
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    usage: UsageStatistics = Field(default_factory=UsageStatistics)
    provider: str
    model: str
    cache_hit: bool = False
    latency_seconds: float = 0.0


class StreamingChunk(BaseModel):
    """A single token delta yielded during streaming."""
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    is_final: bool = False


class ModelMetadata(BaseModel):
    """Metadata regarding limits and cost structures of a specific model."""
    name: str
    context_window: int
    prompt_token_cost_usd_per_million: float = 0.0
    completion_token_cost_usd_per_million: float = 0.0
    supports_tools: bool = True
    supports_streaming: bool = True


class ProviderCapabilities(BaseModel):
    """Capability matrices for a registered provider."""
    supported_models: List[str]
    supports_embeddings: bool = False
    supports_image_input: bool = False
