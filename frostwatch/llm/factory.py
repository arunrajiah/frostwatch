from __future__ import annotations

from typing import TYPE_CHECKING

from frostwatch.llm.base import LLMProvider

if TYPE_CHECKING:
    from frostwatch.core.config import FrostWatchConfig


def get_llm_provider(config: "FrostWatchConfig") -> LLMProvider:
    api_key = config.llm_api_key.get_secret_value()
    model = config.llm_model

    if config.llm_provider == "anthropic":
        from frostwatch.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=api_key, model=model)

    if config.llm_provider == "openai":
        from frostwatch.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key, model=model)

    if config.llm_provider == "gemini":
        from frostwatch.llm.gemini_provider import GeminiProvider
        return GeminiProvider(api_key=api_key, model=model)

    if config.llm_provider == "ollama":
        from frostwatch.llm.ollama_provider import OllamaProvider
        return OllamaProvider(base_url=config.llm_base_url, model=model)

    raise ValueError(f"Unknown LLM provider: {config.llm_provider!r}")
