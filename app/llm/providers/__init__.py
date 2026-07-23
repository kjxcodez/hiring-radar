"""Providers package registering concrete BaseLLMProvider clients."""

from __future__ import annotations

from app.llm.registry import register_provider
from app.llm.providers.openrouter import OpenRouterProvider
from app.llm.providers.google import GoogleProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.groq import GroqProvider
from app.llm.providers.deepseek import DeepSeekProvider
from app.llm.providers.ollama import OllamaProvider

# Register standard catalog
register_provider("openrouter", OpenRouterProvider)
register_provider("google", GoogleProvider)
register_provider("openai", OpenAIProvider)
register_provider("anthropic", AnthropicProvider)
register_provider("groq", GroqProvider)
register_provider("deepseek", DeepSeekProvider)
register_provider("ollama", OllamaProvider)
