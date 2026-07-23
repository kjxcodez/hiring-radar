"""Central LLM Router coordinating cache, budgeting, policies, and fallbacks."""

from __future__ import annotations

import logging
import time
from typing import Iterator, Optional

from app.config import settings, yaml_config
from app.llm.base import BaseLLMProvider
from app.llm.cache import global_llm_cache
from app.llm.compression import compress_history
from app.llm.models import LLMRequest, LLMResponse, StreamingChunk, UsageStatistics
from app.llm.policies import load_routing_policies
from app.llm.registry import get_provider
from app.llm.token_budget import estimate_request_tokens

logger = logging.getLogger(__name__)


class LLMUsageAccumulator:
    """Accumulates system-wide token usage and cost metrics."""

    def __init__(self) -> None:
        self.requests: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.estimated_cost_usd: float = 0.0
        self.cache_hits: int = 0
        self.early_exits: int = 0
        self.failures: int = 0
        self.fallbacks: int = 0
        self.provider_breakdown: dict[str, int] = {}

    def record(self, provider: str, prompt: int, completion: int, cost: float, cache_hit: bool = False) -> None:
        self.requests += 1
        if cache_hit:
            self.cache_hits += 1
        else:
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.total_tokens += (prompt + completion)
            self.estimated_cost_usd += cost
            self.provider_breakdown[provider] = self.provider_breakdown.get(provider, 0) + 1

    def record_early_exit(self) -> None:
        self.requests += 1
        self.early_exits += 1

    def record_failure(self) -> None:
        self.failures += 1

    def record_fallback(self) -> None:
        self.fallbacks += 1

    def clear(self) -> None:
        self.__init__()


global_usage_stats = LLMUsageAccumulator()


class LLMRouter:
    """Orchestrates LLM query executions across multiple providers."""

    @staticmethod
    def complete(request: LLMRequest) -> LLMResponse:
        """Process chat completion request with policy checks, cache lookups, and failover chains."""
        # 1. Load routing policies
        policies = load_routing_policies()
        policy = policies.routing.get(request.task_type)
        
        # If policy is local, bypass LLM
        if policy and policy.provider == "local":
            global_usage_stats.record_early_exit()
            return LLMResponse(
                content="Deterministic local processing executed.",
                provider="local",
                model="local-rule"
            )

        # 2. Dynamic Provider & Model Selection
        preferred_provider = (policy.provider if policy else None) or yaml_config.llm.default_provider or "google"
        preferred_model = (policy.model if policy and policy.model else None) or yaml_config.llm.default_model or "gemini-2.5-flash"
        
        if request.model:
            preferred_model = request.model

        # 3. Token Budgeting & Context Compression
        budget = estimate_request_tokens(request.messages, request.tools)
        if budget.prompt_tokens > 6000:
            # Compress context by trimming old turns
            request.messages = compress_history(request.messages, max_turns=4)

        # 4. Prompt / Response cache check
        cached = global_llm_cache.get(preferred_provider, preferred_model, request.messages, request.tools)
        if cached:
            # Increment metrics
            global_usage_stats.record(preferred_provider, 0, 0, 0.0, cache_hit=True)
            return LLMResponse(
                content=cached.content,
                tool_calls=cached.tool_calls,
                provider=preferred_provider,
                model=preferred_model,
                cache_hit=True,
                usage=cached.usage
            )

        # 5. Formulate fallback chain
        fallback_chain = list(yaml_config.llm.fallback_chain or ["google", "openrouter", "openai", "anthropic", "groq", "ollama"])
        if preferred_provider not in fallback_chain:
            fallback_chain.insert(0, preferred_provider)
            
        # Re-order chain to try preferred provider first
        if preferred_provider in fallback_chain:
            fallback_chain.remove(preferred_provider)
            fallback_chain.insert(0, preferred_provider)

        # 6. Execute fallbacks
        last_exception = None
        executed_provider = None
        executed_model = preferred_model
        
        t0 = time.time()
        for idx, provider_name in enumerate(fallback_chain):
            provider_client = get_provider(provider_name)
            if not provider_client:
                continue

            # Check health/keys configured
            if not provider_client.is_healthy():
                continue

            if idx > 0:
                global_usage_stats.record_fallback()
                # Override model if falling back to other provider
                if provider_name == "google":
                    executed_model = "gemini-2.5-flash"
                elif provider_name == "openai":
                    executed_model = "gpt-4o-mini"
                elif provider_name == "anthropic":
                    executed_model = "claude-3-5-sonnet"
                elif provider_name == "groq":
                    executed_model = "llama-3.3-70b-versatile"
                elif provider_name == "openrouter":
                    executed_model = "openrouter/free"
                else:
                    executed_model = "llama3"

            request.model = executed_model
            logger.info("Routing request to %s (model: %s)", provider_name, executed_model)

            # Retry up to 3 times on transient failures
            for attempt in range(1, 4):
                try:
                    res = provider_client.complete(request)
                    if res.content and res.content.startswith("Error:"):
                        raise RuntimeError(res.content)
                    
                    # Success!
                    executed_provider = provider_name
                    latency = time.time() - t0
                    res.latency_seconds = latency
                    
                    # Estimate cost
                    cost = LLMRouter._estimate_cost(provider_name, executed_model, res.usage.prompt_tokens, res.usage.completion_tokens)
                    res.usage.estimated_cost_usd = cost
                    
                    # Cache successful completion
                    global_llm_cache.set(provider_name, executed_model, request.messages, res, request.tools)
                    
                    # Accumulate global metrics
                    global_usage_stats.record(provider_name, res.usage.prompt_tokens, res.usage.completion_tokens, cost)
                    
                    return res
                except Exception as exc:
                    logger.warning("Attempt %d to %s failed: %s", attempt, provider_name, exc)
                    last_exception = exc
                    global_usage_stats.record_failure()
                    time.sleep(0.5 * attempt)

        # All providers failed
        return LLMResponse(
            content=f"Error: All providers in fallback chain failed. Last error: {last_exception}",
            provider="unknown",
            model="unknown"
        )

    @staticmethod
    def stream(request: LLMRequest) -> Iterator[StreamingChunk]:
        """Stream responses chunk-by-chunk with policy and fallback routing."""
        res = LLMRouter.complete(request)
        if not res.content:
            yield StreamingChunk(content=None, tool_calls=res.tool_calls, is_final=True)
            return

        words = res.content.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield StreamingChunk(content=chunk, is_final=(i == len(words) - 1))

    @staticmethod
    def _estimate_cost(provider: str, model: str, prompt: int, completion: int) -> float:
        """Estimate completion cost in USD."""
        rates = {
            "gemini-2.5-flash": (0.075, 0.30),
            "gemini-2.5-pro": (1.25, 5.00),
            "gpt-4o": (2.50, 10.00),
            "gpt-4o-mini": (0.15, 0.60),
            "claude-3-5-sonnet": (3.00, 15.00),
        }
        
        in_rate, out_rate = 1.0, 3.0
        for m_key, (in_r, out_r) in rates.items():
            if m_key in model:
                in_rate, out_rate = in_r, out_r
                break
                
        if provider in ("groq", "ollama", "local"):
            return 0.0
            
        cost_in = (prompt / 1_000_000.0) * in_rate
        cost_out = (completion / 1_000_000.0) * out_rate
        return cost_in + cost_out
