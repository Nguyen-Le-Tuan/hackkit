"""Run one feature end to end: extract -> validate -> rules -> review flags."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .cache import DiskCache
from .extract import Extraction, extract
from .feature import Feature, RulesResult
from .llm.base import Attachment, LLMClient
from .schemas import Reviewable, ReviewFlag, review_flags_for


@dataclass
class RunResult:
    feature: Feature
    extraction: Extraction
    rules: RulesResult | None = None
    flags: list[ReviewFlag] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.extraction.ok and self.rules is not None


def run_feature(
    feature: Feature,
    client: LLMClient,
    *,
    text: str = "",
    attachments: Sequence[Attachment] = (),
    cache: DiskCache | None = None,
    demo_mode: bool = False,
) -> RunResult:
    extraction = extract(
        client,
        feature.schema,
        instructions=feature.instructions,
        text=text,
        attachments=attachments,
        cache=cache,
        demo_mode=demo_mode,
    )
    if not extraction.ok:
        return RunResult(feature, extraction)
    rules = feature.rules(extraction.data)
    flags = list(rules.flags)
    if isinstance(extraction.data, Reviewable):
        flags = review_flags_for(extraction.data) + flags
    return RunResult(feature, extraction, rules, flags)
