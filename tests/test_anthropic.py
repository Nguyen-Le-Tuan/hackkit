"""Tests our side of the Anthropic integration without depending on SDK internals."""

from types import SimpleNamespace

import pytest

from hackkit.llm import Attachment, LLMError, LLMRequest
from hackkit.llm.anthropic_client import AnthropicClient


class FakeAPIError(Exception):
    pass


class FakeMessages:
    def __init__(self, error: Exception | None = None) -> None:
        self.kwargs: dict = {}
        self.error = error

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        blocks = [SimpleNamespace(type="text", text='{"ok": true}')]
        return SimpleNamespace(content=blocks)


def client_with(messages: FakeMessages) -> AnthropicClient:
    client = AnthropicClient("test-model", api_key="test-key")
    client._client = SimpleNamespace(messages=messages)
    client._anthropic = SimpleNamespace(APIError=FakeAPIError)
    return client


def test_builds_multimodal_request_and_reads_text():
    messages = FakeMessages()
    pdf = Attachment.from_bytes(b"%PDF-1.4", "application/pdf")
    image = Attachment.from_bytes(b"\x89PNG", "image/png")
    response = client_with(messages).complete(
        LLMRequest(system="sys", prompt="hi", attachments=[pdf, image])
    )
    assert response.text == '{"ok": true}'
    blocks = messages.kwargs["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["document", "image", "text"]
    assert blocks[0]["source"]["media_type"] == "application/pdf"
    assert messages.kwargs["system"] == "sys" and messages.kwargs["model"] == "test-model"


def test_api_errors_become_llm_errors():
    client = client_with(FakeMessages(error=FakeAPIError("401 unauthorized")))
    with pytest.raises(LLMError, match="Anthropic API error"):
        client.complete(LLMRequest(system="s", prompt="p"))


def test_missing_model_is_a_clear_error():
    with pytest.raises(LLMError, match="LLM_MODEL"):
        AnthropicClient("", api_key="x")
