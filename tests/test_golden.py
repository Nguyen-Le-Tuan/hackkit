import json

import pytest

from hackkit.golden import assert_close, golden_cases, mismatches


def test_matching_values_pass_within_tolerance():
    actual = {"kwh": 9047.61, "result": {"savings": 1447.6}, "label": "ok"}
    assert_close(actual, {"kwh": 9047.6, "result.savings": 1447.6, "label": "ok"}, rel=1e-4)


def test_mismatches_are_readable():
    problems = mismatches({"kwh": 9000.0}, {"kwh": 9047.6, "incentive": 15600})
    assert problems[0].startswith("kwh: got 9000.0, expected 9047.6 (-0.5")
    assert problems[1] == "incentive: missing (expected 15600)"
    with pytest.raises(AssertionError, match="golden mismatch"):
        assert_close({"kwh": 1}, {"kwh": 2})


def test_golden_cases_load_and_skip_when_absent(tmp_path):
    path = tmp_path / "g.json"
    path.write_text(json.dumps([{"inputs": {"a": 1}, "expected": {"b": 2}}]))
    assert golden_cases(path) == [{"inputs": {"a": 1}, "expected": {"b": 2}, "name": "case 1"}]
    assert golden_cases(tmp_path / "partner" / "missing.json") == []
