"""Measure extraction accuracy on labeled cases. Run: python -m hackkit.evals CASES.jsonl

Each line: {"feature": "receipt", "text": "...", "expected": {"field": value, ...}}
Only top-level fields listed in `expected` are scored. Numbers match within 1%.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings
from .feature import discover
from .llm import get_client
from .pipeline import run_feature


def values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return abs(expected - actual) <= max(0.01, abs(expected) * 0.01)
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    return expected == actual


@dataclass
class EvalReport:
    cases: int = 0
    failed_runs: int = 0
    field_hits: dict[str, int] = field(default_factory=dict)
    field_totals: dict[str, int] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        total = sum(self.field_totals.values())
        return sum(self.field_hits.values()) / total if total else 0.0

    def to_markdown(self) -> str:
        rows = ["| Field | Correct | Total | Accuracy |", "|---|---|---|---|"]
        for name, total in sorted(self.field_totals.items()):
            hits = self.field_hits.get(name, 0)
            rows.append(f"| {name} | {hits} | {total} | {hits / total:.0%} |")
        head = (
            f"Cases: {self.cases}. Failed runs: {self.failed_runs}. "
            f"Field accuracy: {self.accuracy:.1%}."
        )
        return "\n".join([head, "", *rows])


def score(expected: dict[str, Any], actual: dict[str, Any] | None, report: EvalReport) -> None:
    for name, value in expected.items():
        report.field_totals[name] = report.field_totals.get(name, 0) + 1
        if actual is not None and values_match(value, actual.get(name)):
            report.field_hits[name] = report.field_hits.get(name, 0) + 1


def run_eval(cases_path: Path, settings: Settings) -> EvalReport:
    features = discover()
    report = EvalReport()
    for line in cases_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        feature = features[case["feature"]]
        fake = case.get("fake_response", feature.sample_response)
        client = get_client(settings, fake_responder=lambda _req, fake=fake: fake)
        result = run_feature(feature, client, text=case.get("text", ""))
        report.cases += 1
        data = result.extraction.data.model_dump(mode="json") if result.extraction.data else None
        if data is None:
            report.failed_runs += 1
        score(case["expected"], data, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score extraction accuracy on labeled cases.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("--out", type=Path, default=Path("evals/results/latest.md"))
    args = parser.parse_args(argv)
    report = run_eval(args.cases, Settings.from_env())
    text = report.to_markdown()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
