"""Structured extraction: messy input in, validated Pydantic object out.

The LLM only reads and extracts. Anything that must be correct (math, rules, eligibility)
belongs in a feature's deterministic `rules` function.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .cache import DiskCache
from .llm.base import Attachment, LLMClient, LLMError, LLMRequest

T = TypeVar("T", bound=BaseModel)

SYSTEM_TEMPLATE = """You extract structured data from the user's input.
Return ONLY one JSON object that validates against this JSON Schema. No prose, no code fences.
If a value is not present in the input, use null (or an empty list) instead of guessing.

JSON Schema:
{schema}"""


@dataclass
class Extraction(Generic[T]):
    data: T | None
    raw_text: str = ""
    attempts: int = 0
    from_cache: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.data is not None


def strip_to_json(text: str) -> str:
    """Remove code fences or chatter around the first JSON object."""
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text.strip()


def _error_summary(exc: ValidationError, limit: int = 5) -> str:
    parts = [f"{'.'.join(map(str, e['loc'])) or '<root>'}: {e['msg']}" for e in exc.errors()]
    return "; ".join(parts[:limit])


def extract(
    client: LLMClient,
    schema: type[T],
    *,
    instructions: str,
    text: str = "",
    attachments: Sequence[Attachment] = (),
    cache: DiskCache | None = None,
    demo_mode: bool = False,
    max_attempts: int = 2,
    max_tokens: int = 2048,
) -> Extraction[T]:
    schema_json = json.dumps(schema.model_json_schema(), sort_keys=True)
    system = SYSTEM_TEMPLATE.format(schema=schema_json)
    prompt = f"{instructions.strip()}\n\n<input>\n{text}\n</input>"
    # Provider and model are part of the key: a result saved by the fake provider must never be
    # replayed as if a real model had produced it (and vice versa).
    key = DiskCache.make_key(
        getattr(client, "name", "?"),
        getattr(client, "model", "?"),
        schema.__name__,
        schema_json,
        system,
        prompt,
        *(a.data_b64 for a in attachments),
    )

    if cache is not None and (cached := cache.get(key)) is not None:
        try:
            return Extraction(schema.model_validate_json(cached), cached, 0, from_cache=True)
        except ValidationError:
            pass  # schema changed since this was cached; fall through and refresh
    if demo_mode:
        return Extraction(None, error="Demo mode is on and this input has no cached result.")

    raw, error, current_prompt = "", None, prompt
    for attempt in range(1, max_attempts + 1):
        request = LLMRequest(
            system=system,
            prompt=current_prompt,
            attachments=list(attachments),
            max_tokens=max_tokens,
        )
        try:
            raw = client.complete(request).text
        except LLMError as exc:
            error = str(exc)
            continue
        candidate = strip_to_json(raw)
        try:
            data = schema.model_validate_json(candidate)
        except ValidationError as exc:
            error = f"Invalid JSON for {schema.__name__}: {_error_summary(exc)}"
            current_prompt = (
                f"{prompt}\n\nYour previous answer was invalid ({_error_summary(exc)}). "
                "Return only a corrected JSON object."
            )
            continue
        if cache is not None:
            cache.set(key, candidate)
        return Extraction(data, raw, attempt)
    return Extraction(None, raw, max_attempts, error=error)
