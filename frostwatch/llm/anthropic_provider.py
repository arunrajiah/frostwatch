from __future__ import annotations

import anthropic

from frostwatch.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key or None)
        self._model = model or self.default_model()

    def provider_name(self) -> str:
        return "anthropic"

    def default_model(self) -> str:
        return "claude-opus-4-7"

    async def complete(self, prompt: str, system: str = "") -> str:
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            response = await self._client.messages.create(**kwargs)
            return response.content[0].text
        except anthropic.APIError as exc:
            raise RuntimeError(f"Anthropic API error: {exc}") from exc
