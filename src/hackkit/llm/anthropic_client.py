"""Anthropic Messages API client (text, images, PDFs)."""

from __future__ import annotations

from typing import Any

from .base import LLMError, LLMRequest, LLMResponse


class AnthropicClient:
    name = "anthropic"

    def __init__(self, model: str, timeout_s: float = 60.0, api_key: str | None = None) -> None:
        if not model:
            raise LLMError("Set LLM_MODEL in .env to use the anthropic provider.")
        import anthropic  # imported lazily so tests and offline demos never need it

        self._anthropic = anthropic
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=1)

    def complete(self, request: LLMRequest) -> LLMResponse:
        content: list[dict[str, Any]] = []
        for attachment in request.attachments:
            block_type = "document" if attachment.kind == "pdf" else "image"
            content.append(
                {
                    "type": block_type,
                    "source": {
                        "type": "base64",
                        "media_type": attachment.media_type,
                        "data": attachment.data_b64,
                    },
                }
            )
        content.append({"type": "text", "text": request.prompt})
        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=request.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": content}],
            )
        except self._anthropic.APIError as exc:
            raise LLMError(f"Anthropic API error: {exc}") from exc
        text = "".join(block.text for block in message.content if block.type == "text")
        return LLMResponse(text=text, provider=self.name, model=self.model)
