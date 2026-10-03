import json

from pydantic import BaseModel

from hackkit.extract import extract, strip_to_json
from hackkit.llm import FakeClient, LLMError


class Person(BaseModel):
    name: str
    age: int


def test_strip_to_json_removes_fences_and_chatter():
    assert strip_to_json('Sure!\n```json\n{"a": 1}\n```') == '{"a": 1}'


def test_valid_response_on_first_try(cache):
    client = FakeClient(['{"name": "Ana", "age": 30}'])
    result = extract(client, Person, instructions="Get the person.", text="Ana, 30", cache=cache)
    assert result.ok and result.data == Person(name="Ana", age=30)
    assert result.attempts == 1 and not result.from_cache


def test_retries_once_with_validation_feedback():
    client = FakeClient(['{"name": "Ana"}', '{"name": "Ana", "age": 30}'])
    result = extract(client, Person, instructions="Get the person.", text="Ana, 30")
    assert result.ok and result.attempts == 2
    assert "previous answer was invalid" in client.calls[1].prompt


def test_gives_up_after_max_attempts():
    client = FakeClient(["not json", "still not json"])
    result = extract(client, Person, instructions="x", text="y")
    assert not result.ok and "Invalid JSON" in result.error


def test_cache_hit_skips_the_model(cache):
    first = FakeClient(['{"name": "Ana", "age": 30}'])
    extract(first, Person, instructions="x", text="y", cache=cache)
    second = FakeClient([])
    result = extract(second, Person, instructions="x", text="y", cache=cache)
    assert result.from_cache and result.ok and second.calls == []


def test_demo_mode_never_calls_the_model(cache):
    client = FakeClient([])
    result = extract(
        client, Person, instructions="x", text="new input", cache=cache, demo_mode=True
    )
    assert not result.ok and "Demo mode" in result.error and client.calls == []


def test_provider_error_is_reported_not_raised():
    def boom(_request):
        raise LLMError("network down")

    result = extract(FakeClient(boom), Person, instructions="x", text="y")
    assert not result.ok and result.error == "network down"


def test_schema_is_sent_to_the_model():
    client = FakeClient([json.dumps({"name": "Ana", "age": 30})])
    extract(client, Person, instructions="x", text="y")
    assert '"age"' in client.calls[0].system


def test_cache_is_per_provider_and_model(cache):
    """A result saved by the fake provider must not be replayed for a real model."""
    extract(
        FakeClient(['{"name": "Ana", "age": 30}']), Person, instructions="x", text="y", cache=cache
    )

    class RealLooking(FakeClient):
        name, model = "anthropic", "claude-sonnet-5-5"

    real = RealLooking(['{"name": "Bo", "age": 41}'])
    result = extract(real, Person, instructions="x", text="y", cache=cache)
    assert not result.from_cache and result.data == Person(name="Bo", age=41)
    assert len(real.calls) == 1
