"""Turn a run into something a judge or partner can keep: Markdown or JSON."""

from __future__ import annotations

import json
from datetime import datetime

from .pipeline import RunResult


def to_json(result: RunResult) -> str:
    payload = {
        "feature": result.feature.key,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data": result.extraction.data.model_dump(mode="json") if result.extraction.data else None,
        "metrics": result.rules.metrics if result.rules else {},
        "flags": [flag.model_dump() for flag in result.flags],
        "error": result.extraction.error,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def to_markdown(result: RunResult) -> str:
    lines = [f"# {result.feature.title}", ""]
    lines.append(f"Generated {datetime.now():%Y-%m-%d %H:%M}.")
    lines.append("")
    if result.rules and result.rules.summary:
        lines += [result.rules.summary, ""]
    if result.rules and result.rules.metrics:
        lines += ["## Key numbers", ""]
        lines += [f"- {name}: {value}" for name, value in result.rules.metrics.items()]
        lines.append("")
    lines += ["## Needs human review", ""]
    lines += [f"- {f.field}: {f.reason}" for f in result.flags] or ["- Nothing flagged."]
    lines.append("")
    if result.extraction.data is not None:
        data = json.dumps(result.extraction.data.model_dump(mode="json"), indent=2)
        lines += ["## Extracted data", "", "```json", data, "```", ""]
    return "\n".join(lines)
