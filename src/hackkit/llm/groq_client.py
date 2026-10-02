"""Groq client through its OpenAI-compatible Chat Completions API (free tier friendly)."""

from __future__ import annotations

from typing import Any

import httpx

from .base import LLMError, LLMRequest, LLMResponse

GROQ_URL = "https://api.groq.com/openai/v1"


class GroqClient:
    name = "groq"

    def __init__(
        self,
        model: str,
        api_key: str | None,
        timeout_s: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMError("Set GROQ_API_KEY in .env to use the groq provider.")
        if not model:
            raise LLMError("Set GROQ_MODEL in .env to use the groq provider.")
        self.model = model
        self._client = httpx.Client(
            base_url=GROQ_URL,
            timeout=timeout_s,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        if any(a.kind == "pdf" for a in request.attachments):
            raise LLMError("The Groq client cannot read PDFs. Extract the text first.")
        content: str | list[dict[str, Any]] = request.prompt
        if request.attachments:
            content = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{a.media_type};base64,{a.data_b64}"},
                }
                for a in request.attachments
            ] + [{"type": "text", "text": request.prompt}]
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "max_completion_tokens": request.max_tokens,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": content},
            ],
        }
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.model.startswith("openai/gpt-oss"):
            # Extraction needs little reasoning; this saves tokens under free-tier limits.
            payload["reasoning_effort"] = "low"
            payload["include_reasoning"] = False
        try:
            response = self._client.post("/chat/completions", json=payload)
            if response.status_code == 429:
                raise LLMError("Groq rate limit hit (429). Wait a minute or turn on demo mode.")
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"] or ""
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Groq error {exc.response.status_code}: {exc.response.text}") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Groq error: {exc}") from exc
        return LLMResponse(text=text, provider=self.name, model=self.model)
