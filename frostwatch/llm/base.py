from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, prompt: str, system: str = "") -> str: ...

    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def default_model(self) -> str: ...
