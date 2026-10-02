import json

import httpx
import pytest

from hackkit.llm import Attachment, LLMError, LLMRequest
from hackkit.llm.ollama_client import OllamaClient


def test_sends_json_format_and_images():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"a": 1}'}})

    client = OllamaClient("llava", transport=httpx.MockTransport(handler))
    image = Attachment.from_bytes(b"\x89PNG", "image/png")
    response = client.complete(LLMRequest(system="s", prompt="p", attachments=[image]))
    assert response.text == '{"a": 1}'
    assert seen["format"] == "json" and seen["messages"][1]["images"] == [image.data_b64]


def test_rejects_pdf():
    client = OllamaClient("llava", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    pdf = Attachment.from_bytes(b"%PDF", "application/pdf")
    with pytest.raises(LLMError, match="PDF"):
        client.complete(LLMRequest(system="s", prompt="p", attachments=[pdf]))
