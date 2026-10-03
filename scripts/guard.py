#!/usr/bin/env python3
"""Commit and CI guard: stop the files that must never reach a (public) repo.

    python scripts/guard.py --staged     # files in the index; run by scripts/hooks/pre-commit
    python scripts/guard.py --all        # every tracked file; run by CI and `make guard`
    python scripts/guard.py --all --repo PATH   # guard another checkout (used by verify_pr.py)

Checks (rules come from [guard] in hackkit.toml, see scripts/hackkit_config.py):
  blocked-ext   partner documents, archives, media, databases outside [guard].allow
  size          files larger than [guard].max_file_mb
  gitlink       mode 160000 entries (an embedded repo or worktree) without a .gitmodules entry
  symlink       symlinks whose target is absolute or escapes the repo
  blocked-path  [guard].blocked_paths (node_modules, partner/, .env files)
  secret        .env values and well-known key formats (scripts/secret_scan.py); values are
                never printed
  duplicate     identical binary files over 50 KB (warning only)

Content is read from the git index, not the working tree, so `--staged` checks exactly what
will be committed. Exit 0 when clean, 1 on any failure. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hackkit_config  # noqa: E402
import secret_scan  # noqa: E402

DUPLICATE_MIN_BYTES = 50 * 1024
MODE_GITLINK = "160000"
MODE_SYMLINK = "120000"


@dataclass
class Entry:
    """One path in the git index."""

    path: str
    mode: str
    oid: str
    size: int = 0


@dataclass
class Finding:
    check: str
    path: str
    message: str

    def line(self, level: str) -> str:
        return f"{level} [{self.check}] {self.path}: {self.message}"


@dataclass
class GuardResult:
    checked: int = 0
    problems: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


# --------------------------------------------------------------------------- glob matching


@cache
def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Translate a repo glob to a regex: `**` spans folders, `*` and `?` stay in one folder."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            out += "(?:/.*)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out + r"\Z")


def glob_match(path: str, pattern: str) -> bool:
    return bool(_glob_regex(pattern.strip().lstrip("/")).match(path))


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(glob_match(path, p) for p in patterns)


def blocked_path_pattern(path: str, patterns: list[str]) -> str | None:
    """The blocking pattern for `path` (gitignore-style: a later `!pattern` re-allows)."""
    hit: str | None = None
    for pattern in patterns:
        negated = pattern.startswith("!")
        if glob_match(path, pattern[1:] if negated else pattern):
            hit = None if negated else pattern
    return hit


# --------------------------------------------------------------------------- git plumbing


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args], input=data, capture_output=True, check=True
    ).stdout


def index_entries(repo: Path) -> list[Entry]:
    """Every stage-0 entry of the index (`git ls-files -s`)."""
    entries = []
    for record in git(repo, "ls-files", "-s", "-z").split(b"\0"):
        if not record:
            continue
        meta, _, raw_path = record.partition(b"\t")
        mode, oid, stage = meta.decode().split()
        if stage == "0":
            entries.append(Entry(raw_path.decode("utf-8", "surrogateescape"), mode, oid))
    return entries


def staged_paths(repo: Path) -> set[str]:
    """Paths added, copied, modified, renamed or type-changed in the index."""
    out = git(repo, "diff", "--cached", "--name-only", "-z", "--no-renames", "--diff-filter=ACMT")
    return {p.decode("utf-8", "surrogateescape") for p in out.split(b"\0") if p}


def fill_sizes(repo: Path, entries: list[Entry]) -> None:
    blobs = [e for e in entries if e.mode != MODE_GITLINK]
    if not blobs:
        return
    query = "".join(f"{e.oid}\n" for e in blobs).encode()
    lines = git(repo, "cat-file", "--batch-check", data=query).decode().splitlines()
    for entry, line in zip(blobs, lines, strict=False):
        parts = line.split()
        if len(parts) == 3 and parts[2].isdigit():
            entry.size = int(parts[2])


def read_blobs(repo: Path, oids: list[str]) -> dict[str, bytes]:
    """Contents of the given blobs in one `git cat-file --batch` call."""
    if not oids:
        return {}
    unique = list(dict.fromkeys(oids))
    out = git(repo, "cat-file", "--batch", data="".join(f"{o}\n" for o in unique).encode())
    blobs: dict[str, bytes] = {}
    pos = 0
    for oid in unique:
        end = out.index(b"\n", pos)
        header = out[pos:end].split()
        pos = end + 1
        if len(header) != 3:  # "<oid> missing"
            continue
        size = int(header[2])
        blobs[oid] = out[pos : pos + size]
        pos += size + 1
    return blobs


def gitmodules_paths(repo: Path) -> set[str]:
    """Submodule paths registered in the .gitmodules of the index."""
    try:
        out = git(
            repo, "config", "--blob", ":.gitmodules", "--get-regexp", r"^submodule\..*\.path$"
        )
    except subprocess.CalledProcessError:
        return set()
    return {line.split(" ", 1)[1].strip() for line in out.decode().splitlines() if " " in line}


# --------------------------------------------------------------------------- checks


def _ext(path: str) -> str:
    return PurePosixPath(path).suffix.lower()


def check_blocked_extension(entry: Entry, cfg: hackkit_config.GuardConfig) -> Finding | None:
    ext = _ext(entry.path)
    if entry.mode == MODE_GITLINK or ext not in cfg.blocked_extensions:
        return None
    if matches_any(entry.path, cfg.allow):
        return None
    return Finding(
        "blocked-ext",
        entry.path,
        f"{ext} files are blocked (partner documents, archives, media, databases). "
        "Partner documents belong in partner/ which is git-ignored; if this file is public "
        "and needed, add its path to [guard].allow in hackkit.toml",
    )


def check_size(entry: Entry, cfg: hackkit_config.GuardConfig) -> Finding | None:
    limit = cfg.max_file_mb * 1024 * 1024
    if entry.mode == MODE_GITLINK or entry.size <= limit:
        return None
    return Finding(
        "size",
        entry.path,
        f"{entry.size / 1024 / 1024:.1f} MB is over the {cfg.max_file_mb:g} MB limit. Large "
        "files bloat every clone forever: compress it, host it elsewhere and link it, or raise "
        "[guard].max_file_mb in hackkit.toml if it really belongs in git",
    )


def check_gitlink(entry: Entry, submodules: set[str]) -> Finding | None:
    if entry.mode != MODE_GITLINK or entry.path in submodules:
        return None
    return Finding(
        "gitlink",
        entry.path,
        "is a gitlink (mode 160000: an embedded repo or git worktree) with no .gitmodules entry, "
        "so it clones as an empty folder. Remove it with "
        f"`git rm --cached {entry.path}` and add the folder to .gitignore "
        "(or register it properly with `git submodule add <url> <path>`)",
    )


def symlink_escapes(link_path: str, target: str) -> bool:
    """True when a symlink at `link_path` (repo-relative) points outside the repo."""
    if not target or target.startswith(("/", "~", "\\")) or re.match(r"^[A-Za-z]:", target):
        return True
    depth = 0
    for part in [*PurePosixPath(link_path).parent.parts, *target.replace("\\", "/").split("/")]:
        if part in ("", "."):
            continue
        depth = depth - 1 if part == ".." else depth + 1
        if depth < 0:
            return True
    return False


def check_symlink(entry: Entry, target: str) -> Finding | None:
    if entry.mode != MODE_SYMLINK or not symlink_escapes(entry.path, target):
        return None
    return Finding(
        "symlink",
        entry.path,
        f"symlink to '{target}' points outside the repo (absolute or escaping with ..), so it "
        "is broken on every other machine. Remove it with "
        f"`git rm --cached {entry.path}` and add it to .gitignore",
    )


def check_blocked_path(entry: Entry, cfg: hackkit_config.GuardConfig) -> Finding | None:
    pattern = blocked_path_pattern(entry.path, cfg.blocked_paths)
    if pattern is None:
        return None
    if "node_modules" in pattern:
        why = "dependencies are installed (npm ci), never committed"
    elif "partner" in pattern:
        why = "partner/ holds confidential partner files and stays local (it is git-ignored)"
    elif ".env" in pattern:
        why = ".env files hold secrets; commit .env.example with empty values instead"
    else:
        why = "the path matches [guard].blocked_paths in hackkit.toml"
    return Finding(
        "blocked-path",
        entry.path,
        f"{why} (rule {pattern!r}). Remove it with `git rm -r --cached {entry.path}`",
    )


def check_secrets(entry: Entry, content: bytes, secrets: dict[str, str]) -> list[Finding]:
    """Reuse secret_scan.py's .env values and key patterns; never echo the value itself."""
    if entry.mode == MODE_GITLINK or b"\0" in content[:8192]:
        return []
    if len(content) > secret_scan.MAX_FILE_BYTES:
        return []
    found = []
    text = content.decode("utf-8", errors="ignore")
    for number, line in enumerate(text.splitlines(), start=1):
        labels = [f"value of {n} from .env" for n, v in secrets.items() if v in line]
        labels += [label for label, rx in secret_scan.PATTERNS.items() if rx.search(line)]
        for label in labels:
            found.append(
                Finding(
                    "secret",
                    f"{entry.path}:{number}",
                    f"looks like a secret ({label}). Delete it, read it from .env at runtime, "
                    "and rotate the key if it was ever pushed",
                )
            )
    return found


def duplicate_warnings(entries: list[Entry]) -> list[Finding]:
    """Identical files over 50 KB. The git blob id is a content hash, so equal ids = equal bytes."""
    groups: dict[str, list[Entry]] = {}
    for e in entries:
        if e.mode not in (MODE_GITLINK, MODE_SYMLINK) and e.size > DUPLICATE_MIN_BYTES:
            groups.setdefault(e.oid, []).append(e)
    warnings = []
    for same in groups.values():
        if len(same) > 1:
            others = ", ".join(e.path for e in same[1:])
            warnings.append(
                Finding(
                    "duplicate",
                    same[0].path,
                    f"{len(same)} identical copies ({same[0].size // 1024} KB each; also {others})."
                    " Keep one and reference it",
                )
            )
    return warnings


# --------------------------------------------------------------------------- driver


def run_guard(repo: Path, mode: str = "all", env_file: Path | None = None) -> GuardResult:
    """Run every check on the index of `repo`. mode: "all" (tracked files) or "staged"."""
    cfg = hackkit_config.load_config(repo).guard
    entries = index_entries(repo)
    if mode == "staged":
        wanted = staged_paths(repo)
        entries = [e for e in entries if e.path in wanted]
    fill_sizes(repo, entries)
    submodules = gitmodules_paths(repo) if any(e.mode == MODE_GITLINK for e in entries) else set()
    secrets = secret_scan.load_secret_values(env_file or repo / ".env")

    # Read text-ish blobs once: symlink targets and files small enough for the secret scan.
    readable = [
        e
        for e in entries
        if e.mode == MODE_SYMLINK
        or (
            e.mode != MODE_GITLINK
            and e.size <= secret_scan.MAX_FILE_BYTES
            and _ext(e.path) not in cfg.blocked_extensions
        )
    ]
    blobs = read_blobs(repo, [e.oid for e in readable])

    result = GuardResult(checked=len(entries))
    for entry in entries:
        content = blobs.get(entry.oid, b"")
        target = content.decode("utf-8", "surrogateescape") if entry.mode == MODE_SYMLINK else ""
        for finding in (
            check_blocked_path(entry, cfg),
            check_blocked_extension(entry, cfg),
            check_size(entry, cfg),
            check_gitlink(entry, submodules),
            check_symlink(entry, target),
        ):
            if finding:
                result.problems.append(finding)
        if entry.mode != MODE_SYMLINK and entry.oid in blobs:
            result.problems.extend(check_secrets(entry, content, secrets))
    result.warnings.extend(duplicate_warnings(entries))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="check the files staged for commit")
    group.add_argument("--all", action="store_true", help="check every tracked file")
    ap.add_argument("--repo", type=Path, help="repo to check (default: the repo of the cwd)")
    ap.add_argument("--env", type=Path, help=".env whose secret values to look for")
    args = ap.parse_args(argv)

    start = time.monotonic()
    repo = hackkit_config.repo_root(args.repo or Path.cwd())
    mode = "staged" if args.staged else "all"
    try:
        result = run_guard(repo, mode, args.env)
    except (OSError, subprocess.CalledProcessError) as err:
        print(f"guard: cannot read the git index of {repo}: {err}", file=sys.stderr)
        return 2

    for finding in result.problems:
        print(finding.line("FAIL"))
    for finding in result.warnings:
        print(finding.line("WARN"))
    elapsed = time.monotonic() - start
    what = "staged" if args.staged else "tracked"
    summary = (
        f"guard: {result.checked} {what} file(s) checked in {elapsed:.2f}s, "
        f"{len(result.problems)} problem(s), {len(result.warnings)} warning(s)"
    )
    if result.ok:
        print(f"{summary}: PASS")
        return 0
    print(f"{summary}: FAIL")
    if args.staged:
        print(
            "guard: fix the lines above, then commit again. To unstage a file: "
            "`git restore --staged <path>`. CI runs the same checks on every push."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
