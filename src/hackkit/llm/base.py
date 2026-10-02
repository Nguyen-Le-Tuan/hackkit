"""Provider-neutral request/response types. Swap providers without touching feature code."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class LLMError(RuntimeError):
    """Raised when a provider call fails (network, auth, timeout, unsupported input)."""


class Attachment(BaseModel):
    kind: Literal["image", "pdf"]
    media_type: str
    data_b64: str

    @classmethod
    def from_bytes(cls, data: bytes, media_type: str) -> Attachment:
        kind = "pdf" if media_type == "application/pdf" else "image"
        return cls(
            kind=kind, media_type=media_type, data_b64=base64.b64encode(data).decode("ascii")
        )

    @classmethod
    def from_path(cls, path: str | Path) -> Attachment:
        path = Path(path)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return cls.from_bytes(path.read_bytes(), media_type)


class LLMRequest(BaseModel):
    system: str
    prompt: str
    attachments: list[Attachment] = Field(default_factory=list)
    max_tokens: int = 2048
    json_mode: bool = True


class LLMResponse(BaseModel):
    text: str
    provider: str
    model: str


class LLMClient(Protocol):
    name: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...
