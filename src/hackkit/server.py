"""HTTP API + the static web UI in one process.

Run: `make run` (= uvicorn --factory hackkit.server:create_app). The browser app in `web/` calls
the JSON API below; `make snapshot` saves the same responses as files so the UI also runs with
no server at all (GitHub Pages, offline demo).

Endpoints (all JSON):
  GET  /api/health              provider, demo mode, version, feature count
  GET  /api/features            every registered feature (title, inputs, sample text, ...)
  GET  /api/features/{key}      one feature
  POST /api/run/{key}           run a feature: {"text": "...", "attachments": [...]} -> result
  POST /api/narrate/{key}       plain-English explanation of a result, numbers checked by code
  POST /api/cache/clear         forget saved model results
  *    /api/{key}/...           feature-specific routes (Feature.router)
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .cache import DiskCache
from .config import PROVIDERS, Settings
from .export import to_json, to_markdown
from .feature import Feature, discover
from .llm import Attachment, LLMError, get_client
from .narrate import narrate
from .pipeline import RunResult, run_feature

MAX_ATTACHMENT_MB = 15
RESERVED_KEYS = {"health", "features", "run", "cache", "docs", "openapi.json", "narrate", "ask"}


class AttachmentIn(BaseModel):
    media_type: str = Field(description="MIME type, e.g. image/png or application/pdf.")
    data_b64: str = Field(description="File content, base64-encoded.")
    name: str = ""


class NarrateRequest(BaseModel):
    facts: dict[str, Any] = Field(description="Computed values to explain, e.g. the run's metrics.")
    provider: str | None = None
    demo_mode: bool | None = None


class RunRequest(BaseModel):
    text: str = ""
    attachments: list[AttachmentIn] = Field(default_factory=list)
    provider: str | None = Field(default=None, description="Override LLM_PROVIDER for this run.")
    demo_mode: bool | None = Field(default=None, description="Override DEMO_MODE for this run.")


def feature_info(feature: Feature) -> dict[str, Any]:
    return {
        "key": feature.key,
        "title": feature.title,
        "description": feature.description,
        "accepts": list(feature.accepts),
        "sample_text": feature.sample_text,
        "demo_inputs": list(feature.demo_inputs),
        "tags": list(feature.tags),
        "has_routes": feature.router is not None,
        "has_narrative": bool(feature.narrative),
    }


def result_payload(result: RunResult) -> dict[str, Any]:
    """Everything the UI shows for one run, already in display order."""
    extraction = result.extraction
    rules = result.rules
    return {
        "feature": result.feature.key,
        "ok": result.ok,
        "from_cache": extraction.from_cache,
        "attempts": extraction.attempts,
        "error": extraction.error,
        "raw_text": "" if extraction.ok else extraction.raw_text,
        "summary": rules.summary if rules else "",
        "metrics": rules.metrics if rules else {},
        "flags": [flag.model_dump() for flag in result.flags],
        "data": extraction.data.model_dump(mode="json") if extraction.data is not None else None,
        "markdown": to_markdown(result),
        "json": to_json(result),
    }


def _settings_for(base: Settings, request: RunRequest | NarrateRequest) -> Settings:
    settings = base
    if request.provider is not None:
        provider = request.provider.strip().lower()
        if provider not in PROVIDERS:
            raise HTTPException(422, f"provider must be one of {PROVIDERS}")
        settings = replace(settings, llm_provider=provider)
    if request.demo_mode is not None:
        settings = replace(settings, demo_mode=request.demo_mode)
    return settings


def _attachments(items: list[AttachmentIn]) -> list[Attachment]:
    out = []
    for item in items:
        if len(item.data_b64) > MAX_ATTACHMENT_MB * 1024 * 1024 * 4 / 3:
            raise HTTPException(413, f"{item.name or 'attachment'} is over {MAX_ATTACHMENT_MB} MB")
        kind = "pdf" if item.media_type == "application/pdf" else "image"
        out.append(Attachment(kind=kind, media_type=item.media_type, data_b64=item.data_b64))
    return out


def default_web_dir() -> Path:
    return Path(os.getenv("HACKKIT_WEB_DIR", "web"))


def create_app(
    settings: Settings | None = None,
    *,
    features: dict[str, Feature] | None = None,
    web_dir: Path | None = None,
) -> FastAPI:
    """Build the app. Tests pass their own settings/features; uvicorn calls it with none."""
    settings = settings or Settings.from_env()
    features = dict(features) if features is not None else dict(discover())
    web_dir = default_web_dir() if web_dir is None else web_dir

    app = FastAPI(title="hackkit", version=__version__, docs_url="/api/docs", redoc_url=None)
    app.state.settings = settings
    app.state.features = features
    api = APIRouter(prefix="/api")

    def get_feature(key: str) -> Feature:
        if key not in features:
            raise HTTPException(404, f"No feature named {key!r}. Known: {sorted(features)}")
        return features[key]

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "static": False,
            "version": __version__,
            "provider": settings.llm_provider,
            "providers": list(PROVIDERS),
            "demo_mode": settings.demo_mode,
            "features": len(features),
        }

    @api.get("/features")
    def list_features() -> list[dict[str, Any]]:
        return [feature_info(features[key]) for key in sorted(features)]

    @api.get("/features/{key}")
    def one_feature(key: str) -> dict[str, Any]:
        return feature_info(get_feature(key))

    @api.post("/run/{key}")
    def run(key: str, request: RunRequest) -> dict[str, Any]:
        feature = get_feature(key)
        run_settings = _settings_for(settings, request)
        try:
            client = get_client(run_settings, fake_responder=lambda _req: feature.sample_response)
            result = run_feature(
                feature,
                client,
                text=request.text,
                attachments=_attachments(request.attachments),
                cache=DiskCache(run_settings.cache_dir),
                demo_mode=run_settings.demo_mode,
            )
        except LLMError as exc:
            raise HTTPException(502, f"Model call failed: {exc}") from exc
        return result_payload(result)

    @api.post("/narrate/{key}")
    def explain(key: str, request: NarrateRequest) -> dict[str, Any]:
        feature = get_feature(key)
        if not feature.narrative:
            raise HTTPException(404, f"Feature {key!r} has no narrative instructions")
        run_settings = _settings_for(settings, request)
        client = get_client(
            run_settings, fake_responder=lambda _req: feature.sample_narrative or "No sample."
        )
        result = narrate(
            client,
            request.facts,
            instructions=feature.narrative,
            cache=DiskCache(run_settings.cache_dir),
            demo_mode=run_settings.demo_mode,
        )
        return {
            "text": result.text,
            "ok": result.ok,
            "checked": True,
            "fallback": result.fallback,
            "from_cache": result.from_cache,
            "attempts": result.attempts,
            "problems": result.problems,
        }

    @api.post("/cache/clear")
    def clear_cache() -> dict[str, int]:
        return {"removed": DiskCache(settings.cache_dir).clear()}

    app.include_router(api)
    for feature in features.values():
        if feature.key in RESERVED_KEYS:
            raise ValueError(f"Feature key {feature.key!r} clashes with /api/{feature.key}")
        if feature.router is not None:
            app.include_router(feature.router, prefix=f"/api/{feature.key}")
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app
