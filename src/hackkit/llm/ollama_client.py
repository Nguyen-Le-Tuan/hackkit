"""Local fallback via Ollama (no cloud, no API key). Useful if cloud APIs are not allowed."""

from __future__ import annotations

from typing import Any

import httpx

from .base import LLMError, LLMRequest, LLMResponse


class OllamaClient:
    name = "ollama"

    def __init__(
        self,
        model: str,
        url: str = "http://localhost:11434",
        timeout_s: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._client = httpx.Client(base_url=url, timeout=timeout_s, transport=transport)

    def complete(self, request: LLMRequest) -> LLMResponse:
        if any(a.kind == "pdf" for a in request.attachments):
            raise LLMError("The Ollama client cannot read PDFs. Extract the text first.")
        user: dict[str, Any] = {"role": "user", "content": request.prompt}
        images = [a.data_b64 for a in request.attachments if a.kind == "image"]
        if images:
            user["images"] = images
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": request.system}, user],
        }
        if request.json_mode:
            payload["format"] = "json"
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            text = response.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMError(f"Ollama error: {exc}") from exc
        return LLMResponse(text=text, provider=self.name, model=self.model)
