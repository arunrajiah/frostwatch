from __future__ import annotations

import asyncio
import warnings
from concurrent.futures import ThreadPoolExecutor

from frostwatch.llm.base import LLMProvider

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gemini")


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "") -> None:
        self._api_key = api_key
        self._model_name = model or self.default_model()

    def provider_name(self) -> str:
        return "gemini"

    def default_model(self) -> str:
        return "gemini-2.0-flash"

    async def complete(self, prompt: str, system: str = "") -> str:
        def _call() -> str:
            try:
                # Prefer the current google-genai SDK
                import google.genai as genai  # type: ignore[import]

                client = genai.Client(api_key=self._api_key)
                full_prompt = f"{system}\n\n{prompt}" if system else prompt
                response = client.models.generate_content(
                    model=self._model_name, contents=full_prompt
                )
                return response.text
            except ImportError:
                # Fall back to legacy google-generativeai with warning suppressed
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", FutureWarning)
                    import google.generativeai as legacy_genai  # type: ignore[import]

                legacy_genai.configure(api_key=self._api_key)
                model = legacy_genai.GenerativeModel(
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
