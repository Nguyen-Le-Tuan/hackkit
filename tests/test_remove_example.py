"""make remove-example: drop the receipt example everywhere, point pitch scripts at your feature."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import remove_example  # noqa: E402

SHOTS = """[defaults]
sizes = ["1440x900"]

[[shot]]
name = "feature-result"
route = "#/feature/receipt"
steps = [{ click = "#run" }, { wait_for = "[data-result]" }]

[[shot]]
name = "feature-explained"
route = "#/feature/receipt"
steps = [{ click = "text=Explain in plain English" }, { wait_for = ".explain-text" }]
"""
FLOW = """[video]
name = "demo"

[[step]]
goto = "#/feature/receipt"

[[step]]
click = "text=Explain in plain English"

[[step]]
wait_for = ".explain-text"

[[step]]
caption = "Done."
"""


def make_project(tmp_path: Path, mine: str) -> None:
    for key, source in (("receipt", "narrative=NARRATIVE,\n"), ("bill_check", mine)):
        (tmp_path / "src/features" / key).mkdir(parents=True)
        (tmp_path / "src/features" / key / "__init__.py").write_text(source)
    (tmp_path / "evals/cases").mkdir(parents=True)
    (tmp_path / "evals/cases/receipt.jsonl").write_text("{}\n")
    snaps = tmp_path / "web/snapshots"
    (snaps / "runs").mkdir(parents=True)
    (snaps / "runs/receipt.json").write_text("[]")
    (snaps / "runs/bill_check.json").write_text("[]")
    (snaps / "features.json").write_text(json.dumps([{"key": "bill_check"}, {"key": "receipt"}]))
    (snaps / "health.json").write_text(json.dumps({"features": 2}))
    (snaps / "index.json").write_text(json.dumps({"runs": {"receipt": 1, "bill_check": 1}}))
    (tmp_path / "docs/pitch").mkdir(parents=True)
    (tmp_path / "docs/pitch/shots.toml").write_text(SHOTS)
    (tmp_path / "docs/pitch/demo_flow.toml").write_text(FLOW)


def test_removes_the_example_and_retargets_pitch_scripts(tmp_path, monkeypatch):
    make_project(tmp_path, 'narrative="Explain the bill.",\nsample_narrative="x",\n')
    monkeypatch.setattr(remove_example, "ROOT", tmp_path)
    assert remove_example.main([]) == 0
    assert not (tmp_path / "src/features/receipt").exists()
    assert not (tmp_path / "evals/cases/receipt.jsonl").exists()
    snaps = tmp_path / "web/snapshots"
    assert not (snaps / "runs/receipt.json").exists() and (snaps / "runs/bill_check.json").exists()
    assert json.loads((snaps / "features.json").read_text()) == [{"key": "bill_check"}]
    assert json.loads((snaps / "health.json").read_text())["features"] == 1
    assert json.loads((snaps / "index.json").read_text())["runs"] == {"bill_check": 1}
    shots = (tmp_path / "docs/pitch/shots.toml").read_text()
    assert "#/feature/receipt" not in shots and shots.count("#/feature/bill_check") == 2
    assert "Explain" in (tmp_path / "docs/pitch/demo_flow.toml").read_text()  # kept: has narrative
    assert remove_example.main([]) == 0  # safe to run twice


def test_drops_explain_steps_when_the_feature_has_no_narrative(tmp_path, monkeypatch):
    make_project(tmp_path, 'narrative="",\nsample_narrative="We found 1 item.",\n')
    monkeypatch.setattr(remove_example, "ROOT", tmp_path)
    assert remove_example.main(["--feature", "bill_check"]) == 0
    shots = (tmp_path / "docs/pitch/shots.toml").read_text()
    flow = (tmp_path / "docs/pitch/demo_flow.toml").read_text()
    assert 'name = "feature-result"' in shots and "feature-explained" not in shots
    assert "Explain" not in flow and ".explain" not in flow and 'caption = "Done."' in flow


def test_refuses_without_your_own_feature(tmp_path, monkeypatch):
    (tmp_path / "src/features/receipt").mkdir(parents=True)
    (tmp_path / "src/features/receipt/__init__.py").write_text("")
    monkeypatch.setattr(remove_example, "ROOT", tmp_path)
    assert remove_example.main([]) == 2 and (tmp_path / "src/features/receipt").exists()
    assert remove_example.main(["--feature", "nope"]) == 2
