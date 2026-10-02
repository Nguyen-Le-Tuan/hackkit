"""LLM providers behind one interface."""

from __future__ import annotations

from ..config import Settings
from .base import Attachment, LLMClient, LLMError, LLMRequest, LLMResponse
from .fake_client import FakeClient

__all__ = [
    "Attachment",
    "FakeClient",
    "LLMClient",
    "LLMError",
    "LLMRequest",
    "LLMResponse",
    "get_client",
]


def get_client(settings: Settings, fake_responder=None) -> LLMClient:
    """Build the client named by settings.llm_provider."""
    if settings.llm_provider == "anthropic":
        from .anthropic_client import AnthropicClient

        return AnthropicClient(
            settings.llm_model, settings.timeout_s, api_key=settings.anthropic_api_key
        )
    if settings.llm_provider == "ollama":
        from .ollama_client import OllamaClient

        return OllamaClient(settings.ollama_model, settings.ollama_url, settings.timeout_s)
    return FakeClient(fake_responder)
