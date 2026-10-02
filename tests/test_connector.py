import httpx
import pytest

from hackkit.connector import ConnectorError, HttpConnector


def make(handler, **kwargs):
    return HttpConnector(
        "https://api.example.test", transport=httpx.MockTransport(handler), **kwargs
    )


def test_get_json_and_cache(cache):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    api = make(handler, cache=cache)
    assert api.get_json("/status") == {"ok": True}
    assert api.get_json("/status") == {"ok": True}
    assert len(calls) == 1


def test_retries_server_errors(monkeypatch):
    monkeypatch.setattr("hackkit.connector.time.sleep", lambda _s: None)
    responses = iter([httpx.Response(503), httpx.Response(200, json={"v": 1})])
    api = make(lambda _r: next(responses))
    assert api.get_json("/x") == {"v": 1}


def test_client_errors_fail_fast():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404)

    with pytest.raises(ConnectorError):
        make(handler).get_json("/missing")
    assert len(calls) == 1


def test_demo_mode_without_cache_raises(cache):
    api = make(lambda _r: httpx.Response(200, json={}), cache=cache, demo_mode=True)
    with pytest.raises(ConnectorError, match="Demo mode"):
        api.get_json("/never-called")
