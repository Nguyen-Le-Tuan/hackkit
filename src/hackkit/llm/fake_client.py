"""Deterministic client for tests and offline demos. No network, no key, no cost."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .base import LLMError, LLMRequest, LLMResponse

Responder = Callable[[LLMRequest], str]


class FakeClient:
    name = "fake"
    model = "fake"

    def __init__(self, responses: Sequence[str] | Responder | None = None) -> None:
        """`responses` is either a list returned in order, or a function of the request."""
        self.calls: list[LLMRequest] = []
        self._responder: Responder | None = responses if callable(responses) else None
        self._queue = list(responses) if responses is not None and not callable(responses) else []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if self._responder is not None:
            text = self._responder(request)
        elif self._queue:
            text = self._queue.pop(0)
        else:
            raise LLMError("FakeClient has no response configured for this call.")
        return LLMResponse(text=text, provider=self.name, model=self.model)
