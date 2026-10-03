import json

import pytest

from features.receipt import FEATURE as RECEIPT
from hackkit.export import to_json, to_markdown
from hackkit.feature import REGISTRY, discover
from hackkit.llm import FakeClient
from hackkit.pipeline import run_feature


def test_discover_finds_example_feature():
    assert "receipt" in discover()
    assert REGISTRY["receipt"] is RECEIPT


def test_receipt_rules_catch_total_mismatch():
    client = FakeClient(lambda _r: RECEIPT.sample_response)
    result = run_feature(RECEIPT, client, text=RECEIPT.sample_text)
    assert result.ok
    assert result.rules.metrics["computed_total"] == 24.56
    assert any(f.field == "stated_total" for f in result.flags)


def test_low_confidence_adds_review_flags():
    data = json.loads(RECEIPT.sample_response)
    data.update(confidence=0.3, uncertain_fields=["date"])
    result = run_feature(RECEIPT, FakeClient([json.dumps(data)]), text="x")
    fields = [f.field for f in result.flags]
    assert "date" in fields and "*" in fields


def test_exports_include_flags_and_data():
    result = run_feature(RECEIPT, FakeClient(lambda _r: RECEIPT.sample_response), text="x")
    assert "Needs human review" in to_markdown(result)
    assert json.loads(to_json(result))["feature"] == "receipt"


@pytest.mark.parametrize("key", sorted(discover()))
def test_every_feature_runs_offline_on_its_own_sample(key):
    """A new feature's sample_response must validate against its schema, or `make demo` breaks."""
    feature = discover()[key]
    client = FakeClient(lambda _r: feature.sample_response)
    result = run_feature(feature, client, text=feature.sample_text)
    assert result.ok, f"{key}: sample_response does not validate against its schema"
