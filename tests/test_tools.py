import json

import pytest

from hackkit.config import Settings
from hackkit.evals import run_eval, values_match
from hackkit.scaffold import create_extras, create_feature


def test_values_match_tolerates_small_number_differences():
    assert values_match(24.6, 24.6001) and values_match("Corner Market", " corner market ")
    assert not values_match(10, 12)


def test_eval_scores_fields(tmp_path):
    pytest.importorskip("features.receipt")
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        json.dumps(
            {
                "feature": "receipt",
                "text": "x",
                "expected": {"merchant": "Corner Market", "stated_total": 24.6, "tax": 9.99},
            }
        )
    )
    report = run_eval(cases, Settings(llm_provider="fake"))
    assert report.cases == 1 and report.field_totals["tax"] == 1
    assert report.field_hits.get("tax", 0) == 0 and report.field_hits["merchant"] == 1


def test_scaffold_creates_a_valid_feature(tmp_path):
    path = create_feature("intake_triage", "Intake triage", root=tmp_path)
    source = path.read_text()
    assert 'key="intake_triage"' in source and "class IntakeTriageResult" in source
    compile(source, str(path), "exec")


def test_scaffold_extras_write_test_eval_and_page(tmp_path):
    pages = tmp_path / "web" / "js" / "pages"
    pages.mkdir(parents=True)
    (pages / "index.js").write_text("// registry\nexport const pages = [];\n")
    created = create_extras("intake_triage", "Intake triage", tmp_path, page=True)
    names = {p.name for p in created}
    assert {"test_intake_triage.py", "intake_triage.jsonl", "intake_triage.js", "index.js"} <= names
    compile((tmp_path / "tests" / "test_intake_triage.py").read_text(), "t.py", "exec")
    case = json.loads((tmp_path / "evals" / "cases" / "intake_triage.jsonl").read_text())
    assert case["feature"] == "intake_triage"
    registry = (pages / "index.js").read_text()
    assert 'import * as intake_triage from "./intake_triage.js";' in registry
    assert 'path: "/intake_triage"' in registry
    assert create_extras("intake_triage", "Intake triage", tmp_path, page=True) == []  # idempotent
