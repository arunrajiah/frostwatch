from __future__ import annotations

import httpx

from frostwatch.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model or self.default_model()

    def provider_name(self) -> str:
        return "ollama"

    def default_model(self) -> str:
        return "llama3"

    async def complete(self, prompt: str, system: str = "") -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        payload = {
            "model": self._model,
            "prompt": full_prompt,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Ollama API error: {exc}") from exc
