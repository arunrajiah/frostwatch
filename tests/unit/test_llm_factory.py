import pytest
from frostwatch.llm.factory import get_llm_provider
from frostwatch.llm.anthropic_provider import AnthropicProvider
from frostwatch.llm.openai_provider import OpenAIProvider
from frostwatch.llm.gemini_provider import GeminiProvider
from frostwatch.llm.ollama_provider import OllamaProvider


class _Cfg:
    llm_api_key = "test-key"
    llm_model = ""
    llm_base_url = "http://localhost:11434"

    def __init__(self, provider):
        self.llm_provider = provider


def test_returns_anthropic():
    assert isinstance(get_llm_provider(_Cfg("anthropic")), AnthropicProvider)


def test_returns_openai():
    assert isinstance(get_llm_provider(_Cfg("openai")), OpenAIProvider)


def test_returns_gemini():
    assert isinstance(get_llm_provider(_Cfg("gemini")), GeminiProvider)


def test_returns_ollama():
    assert isinstance(get_llm_provider(_Cfg("ollama")), OllamaProvider)


def test_unknown_provider_raises():
    with pytest.raises((ValueError, KeyError, Exception)):
        get_llm_provider(_Cfg("unknown"))


def test_anthropic_default_model():
    p = get_llm_provider(_Cfg("anthropic"))
    assert p.default_model() != ""


def test_openai_default_model():
    p = get_llm_provider(_Cfg("openai"))
    assert p.default_model() != ""
