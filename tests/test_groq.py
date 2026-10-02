import json

import httpx
import pytest

from hackkit.llm import Attachment, LLMError, LLMRequest
from hackkit.llm.groq_client import GroqClient


def ok_response(text: str = '{"a": 1}') -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def test_sends_auth_json_mode_and_images():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return ok_response()

    client = GroqClient("openai/gpt-oss-120b", "test-key", transport=httpx.MockTransport(handler))
    image = Attachment.from_bytes(b"\x89PNG", "image/png")
    response = client.complete(LLMRequest(system="s", prompt="p", attachments=[image]))

    body = seen["body"]
    assert response.text == '{"a": 1}' and response.provider == "groq"
    assert seen["auth"] == "Bearer test-key"
    assert seen["url"].endswith("/openai/v1/chat/completions")
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning_effort"] == "low" and body["include_reasoning"] is False
    assert body["messages"][1]["content"][0]["image_url"]["url"].startswith("data:image/png;")


def test_reasoning_params_only_for_gpt_oss():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return ok_response()

    client = GroqClient("qwen/qwen3.8-27b", "k", transport=httpx.MockTransport(handler))
    client.complete(LLMRequest(system="s", prompt="p"))
    assert "reasoning_effort" not in seen and seen["messages"][1]["content"] == "p"


def test_rate_limit_becomes_llm_error():
    client = GroqClient("m", "k", transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    with pytest.raises(LLMError, match="rate limit"):
        client.complete(LLMRequest(system="s", prompt="p"))


def test_rejects_pdf_and_missing_key():
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqClient("m", None)
    client = GroqClient("m", "k", transport=httpx.MockTransport(lambda r: ok_response()))
    pdf = Attachment.from_bytes(b"%PDF", "application/pdf")
    with pytest.raises(LLMError, match="PDF"):
        client.complete(LLMRequest(system="s", prompt="p", attachments=[pdf]))
