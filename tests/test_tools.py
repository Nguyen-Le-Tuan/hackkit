import json

from hackkit.config import Settings
from hackkit.evals import run_eval, values_match
from hackkit.scaffold import create_feature


def test_values_match_tolerates_small_number_differences():
    assert values_match(24.6, 24.6001) and values_match("Corner Market", " corner market ")
    assert not values_match(10, 12)


def test_eval_scores_fields(tmp_path):
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
