"""Remove the receipt example once your own feature works: `make remove-example [FEATURE=key]`.

The template ships `src/features/receipt/` so everything runs on day one (demo, tests, shots,
deck, video). On event day, after `make feature NAME=<key>`, run this to:

  1. delete src/features/receipt/ and evals/cases/receipt.jsonl;
  2. drop receipt from web/snapshots/ (no model call; re-run `make snapshot` for your feature);
  3. point docs/pitch/shots.toml and demo_flow.toml at #/feature/<your key>; if your feature has
     no `narrative` yet, drop the Explain screenshot and video steps so they cannot fail.

Tests that use the receipt example skip themselves when it is gone. Safe to run twice.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = "receipt"


def features_dir() -> Path:
    return ROOT / "src" / "features"


def other_features() -> list[str]:
    folder = features_dir()
    if not folder.exists():
        return []
    return sorted(
        p.name
        for p in folder.iterdir()
        if p.is_dir() and p.name != EXAMPLE and (p / "__init__.py").exists()
    )


def has_narrative(key: str) -> bool:
    """Cheap check without importing: does the feature set a non-empty narrative?"""
    source = (features_dir() / key / "__init__.py").read_text(encoding="utf-8")
    # \b keeps "sample_narrative=" from counting; an empty "" does not count either.
    return bool(re.search(r"\bnarrative\s*=\s*(?![\"']{2}\s*[,)])\S", source))


def _blocks(text: str, marker: str) -> tuple[str, list[str]]:
    """Split a TOML file into its head and the `[[marker]]` blocks (each block keeps its marker)."""
    parts = re.split(rf"(?m)^(?=\[\[{re.escape(marker)}\]\])", text)
    return parts[0], parts[1:]


def retarget(path: Path, target: str, *, keep_explain: bool, marker: str) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    new = text.replace(f"#/feature/{EXAMPLE}", f"#/feature/{target}")
    notes = []
    if not keep_explain:
        head, blocks = _blocks(new, marker)
        kept = [b for b in blocks if "Explain" not in b and ".explain" not in b]
        if len(kept) != len(blocks):
            notes.append(
                f"{path.relative_to(ROOT)}: dropped {len(blocks) - len(kept)} Explain block(s)"
            )
        new = head + "".join(kept)
    if new != text:
        path.write_text(new, encoding="utf-8")
        notes.insert(0, f"{path.relative_to(ROOT)}: now uses #/feature/{target}")
    return notes


def prune_snapshots(folder: Path) -> list[str]:
    notes = []
    runs = folder / "runs" / f"{EXAMPLE}.json"
    if runs.exists():
        runs.unlink()
        notes.append(f"removed {runs.relative_to(ROOT)}")
    features = folder / "features.json"
    if features.exists():
        data = json.loads(features.read_text(encoding="utf-8"))
        kept = [f for f in data if f.get("key") != EXAMPLE]
        if len(kept) != len(data):
            features.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + "\n", "utf-8")
            notes.append(f"{features.relative_to(ROOT)}: dropped {EXAMPLE}")
        health = folder / "health.json"
        if health.exists():
            info = json.loads(health.read_text(encoding="utf-8"))
            info["features"] = len(kept)
            health.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", "utf-8")
    index = folder / "index.json"
    if index.exists():
        info = json.loads(index.read_text(encoding="utf-8"))
        if info.get("runs", {}).pop(EXAMPLE, None) is not None:
            index.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove the receipt example feature.")
    parser.add_argument("--feature", default="", help="your feature key (default: the first one)")
    parser.add_argument("--force", action="store_true", help="remove even with no other feature")
    args = parser.parse_args(argv)

    others = other_features()
    if args.feature and args.feature not in others:
        print(f"remove-example: no feature {args.feature!r} in src/features/ ({others or 'none'})")
        return 2
    target = args.feature or (others[0] if others else "")
    if not target and not args.force:
        print("remove-example: create your feature first (make feature NAME=<key>), "
              "or pass --force to remove the example anyway.")  # fmt: skip
        return 2

    notes = []
    example = features_dir() / EXAMPLE
    if example.exists():
        shutil.rmtree(example)
        notes.append(f"removed {example.relative_to(ROOT)}/")
    cases = ROOT / "evals" / "cases" / f"{EXAMPLE}.jsonl"
    if cases.exists():
        cases.unlink()
        notes.append(f"removed {cases.relative_to(ROOT)}")
    notes += prune_snapshots(ROOT / "web" / "snapshots")
    if target:
        keep = has_narrative(target)
        pitch = ROOT / "docs" / "pitch"
        notes += retarget(pitch / "shots.toml", target, keep_explain=keep, marker="shot")
        notes += retarget(pitch / "demo_flow.toml", target, keep_explain=keep, marker="step")

    for note in notes or ["nothing to do: the example is already gone"]:
        print(f"remove-example: {note}")
    print("Next: make test, then `make snapshot` (your feature) and `make shots`;")
    print("rewrite the captions in docs/pitch/demo_flow.toml for your story.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
