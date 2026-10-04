"""The HTTP API the web UI talks to (fake provider, no network)."""

import pytest
from fastapi.testclient import TestClient

from hackkit.config import Settings
from hackkit.feature import discover
from hackkit.server import create_app


@pytest.fixture
def client(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>t</title>")
    settings = Settings(llm_provider="fake", cache_dir=tmp_path / "cache")
    return TestClient(create_app(settings, web_dir=web))


def test_health_reports_provider_and_features(client):
    body = client.get("/api/health").json()
    assert body["ok"] and body["provider"] == "fake" and body["features"] >= 1
    assert "anthropic" in body["providers"] and body["static"] is False


def test_features_list_has_the_receipt_example(client):
    keys = [f["key"] for f in client.get("/api/features").json()]
    assert "receipt" in keys
    receipt = client.get("/api/features/receipt").json()
    assert receipt["accepts"] == ["text", "image", "pdf"] and receipt["sample_text"]


def test_run_returns_metrics_flags_and_exports(client):
    receipt = client.get("/api/features/receipt").json()
    body = client.post("/api/run/receipt", json={"text": receipt["sample_text"]}).json()
    assert body["ok"] and body["metrics"]["computed_total"] == 24.56
    assert any("add up to" in flag["reason"] for flag in body["flags"])
    assert (
        body["markdown"].startswith("# Receipt checker") and '"feature": "receipt"' in body["json"]
    )


def test_second_run_is_served_from_cache(client):
    client.post("/api/run/receipt", json={"text": "same input"})
    body = client.post("/api/run/receipt", json={"text": "same input"}).json()
    assert body["from_cache"] and body["attempts"] == 0
    assert client.post("/api/cache/clear").json()["removed"] >= 1


def test_demo_mode_override_never_calls_the_model(client):
    body = client.post("/api/run/receipt", json={"text": "never seen", "demo_mode": True}).json()
    assert not body["ok"] and "Demo mode" in body["error"]


def test_bad_requests_get_clear_errors(client):
    assert client.post("/api/run/nope", json={}).status_code == 404
    assert client.post("/api/run/receipt", json={"provider": "gpt9"}).status_code == 422


def test_attachments_are_accepted(client):
    payload = {
        "text": "x",
        "attachments": [{"media_type": "image/png", "data_b64": "aGVsbG8=", "name": "r.png"}],
    }
    assert client.post("/api/run/receipt", json=payload).json()["ok"]


def test_web_ui_is_served_at_root(client):
    response = client.get("/")
    assert response.status_code == 200 and "<title>t</title>" in response.text


def test_real_web_folder_has_the_app_shell():
    app = create_app(Settings(llm_provider="fake"))
    html = TestClient(app).get("/").text
    assert 'src="js/app.js"' in html and "css/components.css" in html


def test_feature_routes_are_mounted_and_keys_are_checked(tmp_path):
    from dataclasses import replace

    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/hello")
    def hello():
        return {"hi": True}

    receipt = discover()["receipt"]
    custom = replace(receipt, key="custom", router=router)
    app = create_app(Settings(llm_provider="fake"), features={"custom": custom}, web_dir=tmp_path)
    assert TestClient(app).get("/api/custom/hello").json() == {"hi": True}
    with pytest.raises(ValueError, match="clashes"):
        create_app(Settings(), features={"run": replace(receipt, key="run")}, web_dir=tmp_path)


def test_narrate_explains_with_checked_numbers(client):
    receipt = client.get("/api/features/receipt").json()
    assert receipt["has_narrative"]
    run = client.post("/api/run/receipt", json={"text": receipt["sample_text"]}).json()
    assert run["metrics"]["difference"] == 0.04
    body = client.post("/api/narrate/receipt", json={"facts": {"metrics": run["metrics"]}}).json()
    assert body["ok"] and not body["fallback"] and "$24.56" in body["text"]


def test_narrate_rejects_features_without_a_narrative(client):
    assert client.post("/api/narrate/nope", json={"facts": {}}).status_code == 404
