"""Building blocks for feature schemas: confidence and human-review flags."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewFlag(BaseModel):
    field: str
    reason: str


class Reviewable(BaseModel):
    """Inherit from this so every extraction carries the model's own uncertainty."""

    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Your overall confidence from 0 to 1."
    )
    uncertain_fields: list[str] = Field(
        default_factory=list,
        description="Names of fields you guessed or could not read clearly.",
    )


def review_flags_for(model: Reviewable, threshold: float = 0.6) -> list[ReviewFlag]:
    """Turn the model's self-reported uncertainty into flags for a human."""
    flags = [
        ReviewFlag(field=name, reason="Model marked this field as uncertain.")
        for name in model.uncertain_fields
    ]
    if model.confidence < threshold:
        flags.append(
            ReviewFlag(field="*", reason=f"Low overall confidence ({model.confidence:.2f}).")
        )
    return flags
