"""A feature = schema + instructions + deterministic rules. Features self-register."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

from .schemas import ReviewFlag

InputKind = Literal["text", "image", "pdf"]


class RulesResult(BaseModel):
    metrics: dict[str, Any] = Field(default_factory=dict)
    flags: list[ReviewFlag] = Field(default_factory=list)
    summary: str = ""


@dataclass(frozen=True)
class Feature:
    key: str
    title: str
    description: str
    schema: type[BaseModel]
    instructions: str
    rules: Callable[[Any], RulesResult]
    accepts: tuple[InputKind, ...] = ("text",)
    sample_text: str = ""
    sample_response: str = ""  # JSON the fake provider returns, so the demo works offline
    tags: tuple[str, ...] = field(default_factory=tuple)
    # Extra inputs the demo shows; `make snapshot` saves their results for the static site.
    demo_inputs: tuple[str, ...] = field(default_factory=tuple)
    # Optional fastapi.APIRouter with feature-specific endpoints, served under /api/<key>/.
    router: Any = None
    # GET paths under /api/ that `make snapshot` saves too, e.g. ("/api/<key>/top?n=10",).
    snapshot_paths: tuple[str, ...] = field(default_factory=tuple)


REGISTRY: dict[str, Feature] = {}


def register(feature: Feature) -> Feature:
    if feature.key in REGISTRY and REGISTRY[feature.key] is not feature:
        raise ValueError(f"Duplicate feature key: {feature.key}")
    REGISTRY[feature.key] = feature
    return feature


def discover(package: str = "features") -> dict[str, Feature]:
    """Import every module under `package` so their register() calls run."""
    module = importlib.import_module(package)
    for info in pkgutil.iter_modules(module.__path__, prefix=f"{package}."):
        importlib.import_module(info.name)
    return REGISTRY
