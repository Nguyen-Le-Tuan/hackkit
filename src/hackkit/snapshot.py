"""Save API responses as static files, so the web UI runs with no server.

Run: `make snapshot` (= python -m hackkit.snapshot). It calls the real API in-process, with the
provider from .env, for every feature's sample text and `demo_inputs`, plus every GET path in a
feature's `snapshot_paths` (and any `--get` you pass). The browser app (`web/js/api.js`) reads
these files when /api is unreachable: GitHub Pages, a dead Wi-Fi, a laptop with no Python.

Run it once with the real model before the demo, commit `web/snapshots/`, then deploy `web/`.

Layout written under --out (default web/snapshots):
  index.json             what was saved and when
  health.json            like /api/health, with "static": true
  features.json          like /api/features
  runs/<key>.json        [{"text": <input>, "result": <POST /api/run/<key>>, "narration": ...}]
  api/<name>.json        GET responses; <name> = snapshot_name(path), same rule as api.js
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from . import __version__
from .config import Settings


def snapshot_name(path: str) -> str:
    """Map "/api/x/top?n=10&a=b" to "x__top__a-b_n-10" (web/js/api.js uses the same rule)."""
    parts = urlsplit(path)
    route = parts.path
    if route.startswith("/"):
        route = route[1:]
    if route.startswith("api/"):
        route = route[4:]
    name = "__".join(piece for piece in route.split("/") if piece) or "root"
    query = sorted(parse_qsl(parts.query, keep_blank_values=True))
    if query:
        name += "__" + "_".join(f"{key}-{value}" for key, value in query)
    return re.sub(r"[^A-Za-z0-9._-]", "-", name)


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_snapshot(
    out: Path,
    *,
    settings: Settings | None = None,
    features: dict | None = None,
    extra_paths: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Write the snapshot files and return the index. Raises if any call fails."""
    from fastapi.testclient import TestClient

    from .server import create_app

    settings = settings or Settings.from_env()
    app = create_app(settings, features=features, web_dir=Path("/nonexistent"))
    client = TestClient(app)

    if out.exists():
        if any(out.iterdir()) and not (out / "index.json").exists():
            raise FileExistsError(f"{out} is not empty and is not a snapshot folder; refusing")
        shutil.rmtree(out)
    out.mkdir(parents=True)

    health = client.get("/api/health").json()
    health.update(static=True, demo_mode=True)
    _write(out / "health.json", health)
    feature_list = client.get("/api/features").json()
    _write(out / "features.json", feature_list)

    runs: dict[str, int] = {}
    problems: list[str] = []
    paths = list(extra_paths)
    for info in feature_list:
        key = info["key"]
        inputs = [info["sample_text"], *info["demo_inputs"]]
        saved = []
        for text in dict.fromkeys(inputs):
            response = client.post(f"/api/run/{key}", json={"text": text})
            if response.status_code != 200:
                problems.append(f"{key}: HTTP {response.status_code} {response.text[:200]}")
                continue
            result = response.json()
            if not result["ok"]:
                problems.append(f"{key}: run failed: {result['error']}")
            entry = {"text": text, "result": result}
            if info.get("has_narrative") and result["ok"]:
                facts = {"metrics": result["metrics"], "data": result["data"]}
                explained = client.post(f"/api/narrate/{key}", json={"facts": facts})
                if explained.status_code == 200:
                    entry["narration"] = explained.json()
                else:
                    problems.append(f"{key}: narrate HTTP {explained.status_code}")
            saved.append(entry)
        _write(out / "runs" / f"{key}.json", saved)
        runs[key] = len(saved)
        paths += list(app.state.features[key].snapshot_paths)

    saved_paths = []
    for path in dict.fromkeys(paths):
        response = client.get(path)
        if response.status_code != 200:
            problems.append(f"GET {path}: HTTP {response.status_code}")
            continue
        _write(out / "api" / f"{snapshot_name(path)}.json", response.json())
        saved_paths.append(path)

    index = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "version": __version__,
        "provider": settings.llm_provider,
        "runs": runs,
        "paths": saved_paths,
        "problems": problems,
    }
    _write(out / "index.json", index)
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Save API responses for the static web UI.")
    parser.add_argument("--out", type=Path, default=Path("web/snapshots"))
    parser.add_argument("--get", action="append", default=[], help="extra GET path to save")
    args = parser.parse_args(argv)
    index = build_snapshot(args.out, extra_paths=tuple(args.get))
    total = sum(index["runs"].values())
    print(
        f"Saved {total} run(s) for {len(index['runs'])} feature(s) and "
        f"{len(index['paths'])} GET path(s) to {args.out} (provider: {index['provider']})."
    )
    for problem in index["problems"]:
        print(f"  PROBLEM: {problem}")
    if index["provider"] == "fake":
        print("  Note: provider is 'fake'. Run once with the real model before the demo.")
    return 1 if index["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
