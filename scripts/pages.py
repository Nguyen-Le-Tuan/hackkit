"""Publish the static demo (web/ + web/snapshots/) on GitHub Pages: `make pages`.

1. checks web/snapshots/ exists and is committed (the site has no server: it replays snapshots)
2. enables GitHub Pages with "GitHub Actions" as the source (gh api)
3. sets the repo variable PAGES_ENABLED=true so .github/workflows/pages.yml deploys on push
4. starts the workflow now and prints the URL

Free GitHub plans serve Pages only from public repos (`make public`, which runs the guard first).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, check=check)


def main() -> int:
    if not shutil.which("gh"):
        print("pages: the GitHub CLI (gh) is required: https://cli.github.com, then gh auth login")
        return 2
    if not (ROOT / "web" / "snapshots" / "index.json").exists():
        print(
            "pages: web/snapshots/ is missing. "
            "Run `make snapshot` (with the real model) and commit it."
        )
        return 1
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "web/"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    if dirty:
        print("pages: web/ has uncommitted changes; commit and push them first:\n" + dirty)
        return 1
    repo = json.loads(gh("repo", "view", "--json", "nameWithOwner,visibility").stdout)
    name = repo["nameWithOwner"]
    if repo["visibility"] != "PUBLIC":
        print(f"pages: {name} is {repo['visibility'].lower()}. Free plans need a public repo "
              "(make public). Trying anyway.")  # fmt: skip
    existing = gh("api", f"repos/{name}/pages", check=False)
    if existing.returncode != 0:
        created = gh("api", "-X", "POST", f"repos/{name}/pages", "-f", "build_type=workflow",
                     check=False)  # fmt: skip
        if created.returncode != 0:
            print(f"pages: could not enable GitHub Pages: {created.stderr.strip()}")
            return 1
        print("pages: GitHub Pages enabled (source: GitHub Actions)")
    else:
        gh("api", "-X", "PUT", f"repos/{name}/pages", "-f", "build_type=workflow", check=False)
    gh("variable", "set", "PAGES_ENABLED", "--body", "true", check=False)
    run = gh("workflow", "run", "pages.yml", "--ref", "main", check=False)
    if run.returncode != 0:
        print(f"pages: could not start the workflow: {run.stderr.strip()} "
              "(is .github/workflows/pages.yml pushed to main?)")  # fmt: skip
        return 1
    info = gh("api", f"repos/{name}/pages", check=False)
    url = json.loads(info.stdout).get("html_url") if info.returncode == 0 else None
    print(f"pages: deploying. Watch: gh run watch  |  Site: {url or 'see repo Settings > Pages'}")
    print("pages: the site replays web/snapshots/; re-run `make snapshot` and push to update it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
