#!/usr/bin/env python3
"""Keep API keys out of committed files. Standard library only; never prints a secret value.

  secret_scan.py --check-env [--env .env]
      exit 1 if .env holds filled-in secret values (names containing KEY, TOKEN, SECRET,
      PASSWORD...). Used by orchestrate.sh: agents run next to the repo and CAN read ../.env.
  secret_scan.py --repo DIR --since REF [--env PATH]
      scan the files changed since REF (plus untracked files) in a git worktree.
  secret_scan.py [--env PATH] FILE...
      scan the given files.

A scan looks for (a) the values of the secret entries in .env and (b) well-known key formats
(Groq, OpenAI/Anthropic, GitHub, AWS, private-key headers). It prints
`FOUND: <what> in <file>:<line>` and exits 1 when something is found, so a key that an agent
copied into a document is caught before the document is merged or the repo is made public.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL", re.IGNORECASE)
MIN_VALUE_LENGTH = 8
MAX_FILE_BYTES = 2_000_000
PATTERNS = {
    "Groq key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "OpenAI/Anthropic-style key": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    "AWS access key id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Slack token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "private key header": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def load_secret_values(env_path: Path) -> dict[str, str]:
    """Map NAME -> value for the filled-in, secret-looking entries of a .env file."""
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        name, sep, value = line.strip().partition("=")
        value = value.strip().strip("'\"")
        is_secret = sep and not name.startswith("#") and SECRET_NAME.search(name)
        if is_secret and len(value) >= MIN_VALUE_LENGTH:
            values[name.strip()] = value
    return values


def scan_file(path: Path, secrets: dict[str, str]) -> list[tuple[int, str]]:
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        return []
    hits: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for number, line in enumerate(text.splitlines(), start=1):
        hits += [(number, f"value of {name} from .env") for name, v in secrets.items() if v in line]
        hits += [(number, label) for label, rx in PATTERNS.items() if rx.search(line)]
    return hits


def changed_files(repo: Path, since: str) -> list[Path]:
    def git(*args: str) -> list[str]:
        out = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
        ).stdout
        return [line for line in out.splitlines() if line]

    names = set(git("diff", "--name-only", since)) | set(
        git("ls-files", "--others", "--exclude-standard")
    )
    return sorted(repo / n for n in names if not n.startswith(".git/"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--env", type=Path, default=Path(".env"))
    ap.add_argument("--check-env", action="store_true", help="fail if .env holds filled secrets")
    ap.add_argument("--repo", type=Path)
    ap.add_argument("--since", help="git ref; with --repo, scan files changed since it")
    args = ap.parse_args(argv)

    secrets = load_secret_values(args.env)
    if args.check_env:
        for name in secrets:
            print(f"FILLED: {name}")
        if not secrets:
            print(f"no filled secret values in {args.env}")
        return 1 if secrets else 0

    try:
        files = changed_files(args.repo, args.since) if args.repo else list(args.files)
    except (subprocess.CalledProcessError, FileNotFoundError, TypeError) as err:
        print(f"secret_scan: cannot list files: {err}", file=sys.stderr)
        return 2
    base = args.repo or Path()
    found = 0
    for path in files:
        for number, label in scan_file(path, secrets):
            shown = path.relative_to(base) if path.is_relative_to(base) else path
            print(f"FOUND: {label} in {shown}:{number}")
            found += 1
    if not found:
        print(f"clean ({len(files)} file(s) scanned)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
