from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import google.generativeai as genai

from frostwatch.llm.base import LLMProvider

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gemini")


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        genai.configure(api_key=api_key)
        self._model_name = model or self.default_model()

    def provider_name(self) -> str:
        return "gemini"

    def default_model(self) -> str:
        return "gemini-1.5-pro"

    async def complete(self, prompt: str, system: str = "") -> str:
        def _call() -> str:
            model = genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=system if system else None,
            )
            response = model.generate_content(prompt)
            return response.text

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(_executor, _call)
        except Exception as exc:
            raise RuntimeError(f"Gemini API error: {exc}") from exc
