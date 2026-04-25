from __future__ import annotations

from openai import APIError, AsyncOpenAI

from frostwatch.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        self._client = AsyncOpenAI(api_key=api_key or None)
        self._model = model or self.default_model()

    def provider_name(self) -> str:
        return "openai"

    def default_model(self) -> str:
        return "gpt-4o"

    async def complete(self, prompt: str, system: str = "") -> str:
        from openai.types.chat import ChatCompletionMessageParam

        messages: list[ChatCompletionMessageParam] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""
        except APIError as exc:
            raise RuntimeError(f"OpenAI API error: {exc}") from exc
