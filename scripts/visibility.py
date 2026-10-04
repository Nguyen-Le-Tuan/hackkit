#!/usr/bin/env python3
"""Switch the GitHub repo between private and public, after a confirmation. (`make private|public`)

    python scripts/visibility.py private
    python scripts/visibility.py public [--yes]

The trade-off: Devpost judges (and most hackathon rules) need a PUBLIC repo at submission time,
but partner files, transcripts and half-finished secrets must never be public. Work PRIVATE
during the event and go PUBLIC only after `guard.py --all` passes. Going public first runs the
guard on every tracked file and lists blocked files that are still in the git HISTORY: a
public repo exposes every past commit, not just the current tree.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402
import hackkit_config  # noqa: E402

TRADE_OFF = """\
Trade-off:
  public  = judges (Devpost) can open the code; required by most hackathons at submission.
            EVERYTHING in the history becomes readable by anyone, forever (forks, caches).
  private = partner/confidential files and work in progress stay hidden; judges cannot see it.
"""


def history_leaks(repo: Path, cfg: hackkit_config.GuardConfig) -> list[str]:
    """Paths ever added in any commit that the guard would block now."""
    proc = subprocess.run(
        ["git", "log", "--all", "--diff-filter=A", "--name-only", "--format="],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    leaks = set()
    for path in proc.stdout.splitlines():
        if not path:
            continue
        ext = Path(path).suffix.lower()
        blocked_ext = ext in cfg.blocked_extensions and not guard.matches_any(path, cfg.allow)
        if blocked_ext or guard.blocked_path_pattern(path, cfg.blocked_paths):
            leaks.add(path)
    return sorted(leaks)


def set_visibility(root: Path, visibility: str) -> int:
    """`gh repo edit --visibility`; older gh (< 2.50) lacks the confirmation flag, so fall back to
    the REST API (`PATCH repos/{owner}/{repo}`), which every gh version can call."""
    proc = subprocess.run(
        [
            "gh",
            "repo",
            "edit",
            "--visibility",
            visibility,
            "--accept-visibility-change-consequences",
        ],  # fmt: skip
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return 0
    name = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not name:
        print(proc.stderr.strip() or "gh could not find this repo (gh auth status?)")
        return proc.returncode or 1
    api = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "PATCH",
            f"repos/{name}",
            "-f",
            f"visibility={visibility}",
            "-q",
            ".visibility",
        ],  # fmt: skip
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if api.returncode != 0 or api.stdout.strip() != visibility:
        print(api.stderr.strip() or proc.stderr.strip())
        return api.returncode or 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("visibility", choices=["private", "public"])
    ap.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = ap.parse_args(argv)

    root = hackkit_config.repo_root(Path.cwd())
    if not shutil.which("gh"):
        print("visibility: GitHub CLI `gh` is not installed (https://cli.github.com)")
        return 2
    print(TRADE_OFF)
    if args.visibility == "public":
        result = guard.run_guard(root, "all")
        for finding in result.problems:
            print(finding.line("FAIL"))
        if not result.ok:
            print("visibility: the guard failed on the current tree; fix it before going public.")
            return 1
        leaks = history_leaks(root, hackkit_config.load_config(root).guard)
        if leaks:
            print("These blocked files are still in the git HISTORY and would become public:")
            for path in leaks[:20]:
                print(f"  {path}")
            print(
                "Rewrite the history first (git filter-repo --invert-paths --path <file>) or "
                "publish a fresh repo with a clean history."
            )
    if not args.yes:
        try:
            answer = input(f"Make this repo {args.visibility.upper()}? Type 'yes' to confirm: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "yes":
            print("cancelled")
            return 1
    code = set_visibility(root, args.visibility)
    if code == 0:
        print(f"repo is now {args.visibility}")
    return code


if __name__ == "__main__":
    sys.exit(main())
