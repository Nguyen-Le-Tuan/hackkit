"""Golden tests: prove your code reproduces the partner's own numbers.

At UB AI for Good 2026 this is what made the calculator trustworthy: the partner's spreadsheet
example, re-computed by our code, matched to the cent. Put the partner's worked examples in a
JSON file and let pytest check every field:

    tests/golden/quote.json
    [{"name": "partner example", "inputs": {...}, "expected": {"kwh": 9047.6, "savings": 1447.6}}]

    from hackkit.golden import golden_cases, assert_close

    CASES = golden_cases("tests/golden/quote.json")

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
    def test_matches_partner_sheet(case):
        result = estimate(**case["inputs"])
        assert_close(result.model_dump(), case["expected"], rel=1e-3)

Only fields listed in "expected" are checked, so the golden file can stay small. Never put
partner-confidential numbers in a public repo without permission (keep them in partner/ and
point the test there; it skips when the file is absent).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _get(data: Mapping[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        elif isinstance(value, list | tuple) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise KeyError(dotted)
    return value


def mismatches(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    rel: float = 1e-6,
    abs_tol: float = 1e-9,
) -> list[str]:
    """Readable differences; keys in `expected` may be dotted paths ("result.kwh")."""
    problems = []
    for key, want in expected.items():
        try:
            got = _get(actual, key)
        except KeyError:
            problems.append(f"{key}: missing (expected {want!r})")
            continue
        if isinstance(want, int | float) and not isinstance(want, bool):
            if not isinstance(got, int | float) or not math.isclose(
                got, want, rel_tol=rel, abs_tol=abs_tol
            ):
                diff = (
                    f" ({(got - want) / want:+.4%})"
                    if isinstance(got, int | float) and want
                    else ""
                )
                problems.append(f"{key}: got {got!r}, expected {want!r}{diff}")
        elif got != want:
            problems.append(f"{key}: got {got!r}, expected {want!r}")
    return problems


def assert_close(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    rel: float = 1e-6,
    abs_tol: float = 1e-9,
) -> None:
    problems = mismatches(actual, expected, rel=rel, abs_tol=abs_tol)
    if problems:
        raise AssertionError("golden mismatch:\n  " + "\n  ".join(problems))


def golden_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load cases; returns [] (so parametrize skips) when the file is absent, e.g. partner/."""
    path = Path(path)
    if not path.exists():
        return []
    cases = json.loads(path.read_text(encoding="utf-8"))
    for i, case in enumerate(cases):
        if "expected" not in case:
            raise ValueError(f"{path}: case {i} has no 'expected'")
        case.setdefault("name", f"case {i + 1}")
        case.setdefault("inputs", {})
    return cases
