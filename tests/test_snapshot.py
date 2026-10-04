"""Static snapshots let the web UI run with no server (GitHub Pages, offline)."""

import json
from pathlib import Path

import pytest

from hackkit.config import Settings
from hackkit.snapshot import build_snapshot, snapshot_name

SHARED = Path(__file__).resolve().parents[1] / "web" / "tests" / "snapshot_names.json"


@pytest.mark.parametrize(("path", "expected"), json.loads(SHARED.read_text()))
def test_snapshot_name_matches_the_js_rule(path, expected):
    assert snapshot_name(path) == expected


def test_build_snapshot_writes_every_file(tmp_path):
    out = tmp_path / "snapshots"
    settings = Settings(llm_provider="fake", cache_dir=tmp_path / "cache")
    index = build_snapshot(out, settings=settings)
    assert index["runs"]["receipt"] >= 1 and index["problems"] == []
    health = json.loads((out / "health.json").read_text())
    assert health["static"] is True
    runs = json.loads((out / "runs" / "receipt.json").read_text())
    assert runs[0]["result"]["metrics"]["computed_total"] == 24.56
    assert runs[0]["narration"]["ok"] and "$24.60" in runs[0]["narration"]["text"]
    assert {f["key"] for f in json.loads((out / "features.json").read_text())} >= {"receipt"}


def test_build_snapshot_refuses_to_wipe_a_foreign_folder(tmp_path):
    folder = tmp_path / "important"
    folder.mkdir()
    (folder / "notes.txt").write_text("keep me")
    with pytest.raises(FileExistsError):
        build_snapshot(folder, settings=Settings(llm_provider="fake", cache_dir=tmp_path / "c"))
    assert (folder / "notes.txt").exists()
