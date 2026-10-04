"""Where a number came from, as data (not "[tag]" strings glued into text).

Every value a judge can see should say its source. Keep the source next to the value:

    from hackkit.provenance import Sourced, source, DEMO

    floors = Sourced(value=11, source=source("OpenStreetMap", 0.9, note="building:levels"))
    cost = Sourced(value=8.0, source=source(DEMO, note="team-chosen $/sq ft"))

The web UI renders any {"value": ..., "source": {...}} it receives with a source badge, and
values whose source is demo in red (web/js/ui.js: sourcedView). Reports and CSV can use
`label()` / `as_row()`, so each medium formats the same data its own way.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

# Standard source names. Use your own for real sources ("OpenStreetMap", "Census geocoder").
ASSUMED = "assumed"  # a default the team chose; say so on screen
USER = "user input"  # typed by the person using the app
MODEL = "model"  # extracted by the LLM from the input (pair with a confidence)
COMPUTED = "computed"  # derived by deterministic code from other sourced values
DEMO = "demo"  # illustrative, made up for the demo: always shown in red


class Provenance(BaseModel):
    source: str = Field(description="Short name of the source, e.g. 'OpenStreetMap'.")
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    note: str = Field(default="", description="Detail: field name, formula, dataset id...")
    url: str | None = None

    @property
    def is_demo(self) -> bool:
        return self.source.strip().lower() == DEMO

    @property
    def is_assumed(self) -> bool:
        return self.source.strip().lower() in {ASSUMED, DEMO}

    def label(self) -> str:
        """'OpenStreetMap (0.90)' / 'demo value' — one readable string for text and CSV."""
        if self.is_demo:
            return "DEMO value"
        if self.confidence is None:
            return self.source
        return f"{self.source} ({self.confidence:.2f})"


class Sourced(BaseModel, Generic[T]):
    """A value plus where it came from."""

    value: T
    source: Provenance

    def as_row(self, name: str) -> dict[str, Any]:
        """Flat dict for tables and CSV: name, value, source, confidence, note, demo."""
        return {
            "name": name,
            "value": self.value,
            "source": self.source.source,
            "confidence": self.source.confidence,
            "note": self.source.note,
            "demo": self.source.is_demo,
        }


def source(name: str, confidence: float | None = None, *, note: str = "", url: str | None = None):
    """Shorthand: source("OpenStreetMap", 0.9, note="way 123")."""
    return Provenance(source=name, confidence=confidence, note=note, url=url)


def sourced(value: T, name: str, confidence: float | None = None, *, note: str = "") -> Sourced[T]:
    """Shorthand: sourced(11, "OpenStreetMap", 0.9)."""
    return Sourced[type(value)](value=value, source=source(name, confidence, note=note))


def demo_values(values: dict[str, Sourced]) -> list[str]:
    """Names of the values that are made up: list them in the UI legend and the pitch."""
    return [name for name, item in values.items() if item.source.is_demo]
