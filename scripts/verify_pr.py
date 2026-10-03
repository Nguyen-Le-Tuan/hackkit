#!/usr/bin/env python3
"""Verify a pull request the way the integrator would, in a throw-away worktree.

    python scripts/verify_pr.py 12              # make verify PR=12
    python scripts/verify_pr.py 12 --comment    # also post the report as a PR comment
    python scripts/verify_pr.py --local agent/x # a local branch, no gh, no network
    python scripts/verify_pr.py --local agent/x --base-ref main

Steps (each PASS / FAIL / SKIP with its duration):
  target branch  the PR must target [verify].base_branch (default main), not another feature
                 branch: a stacked PR merged into its parent never reaches main
  merge          temporary worktree at origin/<base> + `git merge --no-edit <PR head>`
  guard          scripts/guard.py --all on the merged tree
  ruff check / ruff format   lint and format check (the repo venv's ruff when present)
  pytest         against the WORKTREE code (PYTHONPATH=<wt>/src:<wt>, cwd=<wt>)
  forbidden      [verify].forbid_patterns on the lines the PR adds
  smoke          GET /api/health and / through FastAPI's TestClient (when the server exists)

Prints a Markdown table and `VERDICT: MERGE OK` or `VERDICT: DO NOT MERGE (n problems)`.
Exit 0 = merge OK, 1 = do not merge, 2 = could not run (gh missing, not logged in...).
The temporary worktree is always removed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hackkit_config  # noqa: E402

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
PR_FIELDS = (
    "number,title,baseRefName,headRefName,headRefOid,mergeable,files,isCrossRepository,state"
)
SCRIPTS = Path(__file__).resolve().parent
STEP_TIMEOUT_S = 900
SMOKE_SNIPPET = """
from fastapi.testclient import TestClient
from hackkit.server import create_app

client = TestClient(create_app())
bad = []
for path in ("/api/health", "/"):
    status = client.get(path).status_code
    print(f"GET {path} -> {status}")
    if status != 200:
        bad.append(f"{path}={status}")
raise SystemExit(1 if bad else 0)
"""


class VerifyError(Exception):
    """A precondition failed (gh missing, not logged in, unknown branch...)."""


@dataclass
class Step:
    name: str
    result: str
    seconds: float = 0.0
    note: str = ""


# --------------------------------------------------------------------------- pure logic


def check_base(pr: dict, base_branch: str) -> Step:
    """The stacked-PR check: a PR must target the base branch."""
    number, base = pr.get("number", "?"), pr.get("baseRefName", "")
    if base == base_branch:
        return Step("target branch", PASS, note=f"targets {base_branch}")
    return Step(
        "target branch",
        FAIL,
        note=(
            f"this PR targets {base!r}, not {base_branch}: re-target it with "
            f"`gh pr edit {number} --base {base_branch}` (a PR merged into another feature "
            f"branch never reaches {base_branch})"
        ),
    )


def check_state(pr: dict) -> Step:
    notes = []
    result = PASS
    if pr.get("state", "OPEN") != "OPEN":
        result = FAIL
        notes.append(f"PR is {pr.get('state')}")
    if pr.get("mergeable") == "CONFLICTING":
        notes.append("GitHub reports conflicts")
    if pr.get("isCrossRepository"):
        notes.append("from a fork: read the diff before running its code")
    files = pr.get("files") or []
    notes.append(f"{len(files)} file(s), head {pr.get('headRefName', '?')}")
    return Step("pull request", result, note="; ".join(notes))


def added_lines(diff_text: str) -> list[tuple[str, int, str]]:
    """(file, new line number, text) for every line a unified diff adds."""
    out: list[tuple[str, int, str]] = []
    current, number = "", 0
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            name = line[4:].strip()
            current = name[2:] if name.startswith("b/") else name
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            number = int(m.group(1)) if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            out.append((current, number, line[1:]))
            number += 1
        elif line.startswith(" "):
            number += 1
    return out


def find_forbidden(diff_text: str, patterns: list[str]) -> list[str]:
    """`file:line matches /pattern/` for each added line matching a forbidden regex.

    The matched text itself is not repeated (it may be a name that must not spread further).
    """
    compiled = []
    for p in patterns:
        try:
            compiled.append((p, re.compile(p)))
        except re.error as err:
            compiled.append((p, None))
            print(f"verify: bad [verify].forbid_patterns regex {p!r}: {err}", file=sys.stderr)
    hits = []
    for name, number, text in added_lines(diff_text):
        for p, rx in compiled:
            if rx is not None and rx.search(text):
                hits.append(f"{name}:{number} matches /{p}/")
    return hits


def problems(steps: list[Step]) -> int:
    return sum(1 for s in steps if s.result == FAIL)


def verdict(steps: list[Step]) -> str:
    n = problems(steps)
    return "VERDICT: MERGE OK" if n == 0 else f"VERDICT: DO NOT MERGE ({n} problems)"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_summary(steps: list[Step], title: str) -> str:
    """Markdown report: heading, one table row per step, verdict line."""
    rows = [
        f"### {title}",
        "",
        "| step | result | time | note |",
        "|---|---|---|---|",
    ]
    for s in steps:
        rows.append(f"| {_cell(s.name)} | {s.result} | {s.seconds:.1f}s | {_cell(s.note)} |")
    rows += ["", verdict(steps)]
    return "\n".join(rows)


def pytest_summary(output: str) -> str:
    """`N passed in Xs` from pytest output, or a count of the progress dots under -qq."""
    for line in reversed(output.splitlines()):
        if re.search(r"\d+ (passed|failed|error)", line):
            return line.strip(" =")
    progress = [ln for ln in output.splitlines() if re.fullmatch(r"[.sxFE]+\s*(\[\s*\d+%\])?", ln)]
    dots = sum(ln.split("[")[0].count(".") for ln in progress)
    return f"{dots} passed" if progress else tail(output, 1)


def tail(text: str, lines: int = 3, width: int = 300) -> str:
    kept = [ln.strip() for ln in text.strip().splitlines() if ln.strip()][-lines:]
    return " / ".join(kept)[-width:]


# --------------------------------------------------------------------------- process helpers


def run(
    cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: float = STEP_TIMEOUT_S
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False
    )


def git(repo: Path, *args: str) -> str:
    proc = run(["git", *args], cwd=repo, timeout=300)
    if proc.returncode != 0:
        raise VerifyError(f"`git {' '.join(args)}` failed: {tail(proc.stderr or proc.stdout)}")
    return proc.stdout.strip()


def timed(name: str, fn: Callable[[], tuple[str, str]]) -> Step:
    start = time.monotonic()
    try:
        result, note = fn()
    except subprocess.TimeoutExpired:
        result, note = FAIL, "timed out"
    except (OSError, VerifyError) as err:
        result, note = FAIL, str(err)
    return Step(name, result, time.monotonic() - start, note)


def venv_python(root: Path) -> str:
    candidate = root / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def find_ruff(root: Path) -> list[str] | None:
    candidate = root / ".venv" / "bin" / "ruff"
    if candidate.exists():
        return [str(candidate)]
    if shutil.which("ruff"):
        return ["ruff"]
    probe = run([sys.executable, "-m", "ruff", "--version"], cwd=root, timeout=30)
    return [sys.executable, "-m", "ruff"] if probe.returncode == 0 else None


def worktree_env(wt: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(wt / "src"), str(wt)])
    env["LLM_PROVIDER"] = "fake"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


# --------------------------------------------------------------------------- steps on the worktree


def step_guard(wt: Path, root: Path) -> tuple[str, str]:
    proc = run([venv_python(root), str(SCRIPTS / "guard.py"), "--all", "--repo", str(wt)], wt)
    fails = [ln for ln in proc.stdout.splitlines() if ln.startswith("FAIL")]
    if proc.returncode == 0:
        return PASS, tail(proc.stdout, 1)
    return FAIL, tail("\n".join(fails) or proc.stdout + proc.stderr, 3)


def step_ruff(wt: Path, root: Path, args: list[str]) -> tuple[str, str]:
    ruff = find_ruff(root)
    if ruff is None:
        return SKIP, "ruff not installed (pip install -e .[dev])"
    proc = run([*ruff, *args, "--no-cache", "."], wt)
    return (PASS if proc.returncode == 0 else FAIL), tail(proc.stdout + proc.stderr, 2)


def step_pytest(wt: Path, root: Path) -> tuple[str, str]:
    py, env = venv_python(root), worktree_env(wt)
    if (wt / "src" / "hackkit").is_dir():  # make sure the tests import the WORKTREE code
        probe = run([py, "-c", "import hackkit; print(hackkit.__file__)"], wt, env, 60)
        where = Path(probe.stdout.strip() or ".").resolve()
        if probe.returncode == 0 and not where.is_relative_to(wt.resolve()):
            return FAIL, f"hackkit resolves to {where}, not the worktree"
    proc = run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], wt, env)
    summary = pytest_summary(proc.stdout)
    if proc.returncode == 5:
        return SKIP, "no tests collected"
    if proc.returncode == 0:
        return PASS, summary
    if "No module named pytest" in proc.stderr:
        return SKIP, "pytest not installed (pip install -e .[dev])"
    return FAIL, tail(proc.stdout + proc.stderr, 3)


def step_forbidden(wt: Path, base_ref: str, head: str, patterns: list[str]) -> tuple[str, str]:
    if not patterns:
        return SKIP, "no [verify].forbid_patterns in hackkit.toml"
    diff = git(wt, "diff", "--no-color", "--no-ext-diff", f"{base_ref}...{head}")
    hits = find_forbidden(diff, patterns)
    if not hits:
        return PASS, f"{len(patterns)} pattern(s), 0 hits"
    more = f" (+{len(hits) - 3} more)" if len(hits) > 3 else ""
    return FAIL, "; ".join(hits[:3]) + more


def step_smoke(wt: Path, root: Path, enabled: bool) -> tuple[str, str]:
    if not enabled:
        return SKIP, "disabled by [verify].smoke"
    if not (wt / "src" / "hackkit" / "server.py").exists():
        return SKIP, "no src/hackkit/server.py yet"
    py, env = venv_python(root), worktree_env(wt)
    if run([py, "-c", "import fastapi, httpx"], wt, env, 60).returncode != 0:
        return SKIP, "fastapi/httpx not installed in this venv"
    proc = run([py, "-c", SMOKE_SNIPPET], wt, env, 120)
    return (PASS if proc.returncode == 0 else FAIL), tail(proc.stdout + proc.stderr, 2)


# --------------------------------------------------------------------------- orchestration


def verify_merge(
    root: Path, base_ref: str, head: str, cfg: hackkit_config.Config, steps: list[Step]
) -> None:
    """Merge `head` into `base_ref` in a temp worktree and run every check there."""
    tmp = Path(tempfile.mkdtemp(prefix="hackkit-verify-"))
    wt = tmp / "wt"
    try:
        start = time.monotonic()
        git(root, "worktree", "add", "--detach", "--quiet", str(wt), base_ref)
        merge = run(
            [
                "git",
                "-c",
                "user.name=hackkit-verify",
                "-c",
                "user.email=verify@localhost",
                "-c",
                "core.hooksPath=/dev/null",
                "merge",
                "--no-edit",
                "--no-ff",
                "--quiet",
                head,
            ],
            wt,
            timeout=300,
        )
        if merge.returncode != 0:
            conflicts = run(["git", "diff", "--name-only", "--diff-filter=U"], wt).stdout.split()
            note = (
                f"conflicts in {', '.join(conflicts)}: the author must merge {base_ref} into "
                "the branch and resolve them"
                if conflicts
                else tail(merge.stderr + merge.stdout)
            )
            steps.append(Step("merge", FAIL, time.monotonic() - start, note))
            run(["git", "merge", "--abort"], wt)
            steps.append(Step("checks", SKIP, note="skipped: the merge failed"))
            return
        steps.append(Step("merge", PASS, time.monotonic() - start, f"clean merge into {base_ref}"))
        steps.append(timed("guard", lambda: step_guard(wt, root)))
        steps.append(timed("ruff check", lambda: step_ruff(wt, root, ["check"])))
        steps.append(timed("ruff format", lambda: step_ruff(wt, root, ["format", "--check"])))
        steps.append(timed("pytest", lambda: step_pytest(wt, root)))
        steps.append(
            timed(
                "forbidden",
                lambda: step_forbidden(wt, base_ref, head, cfg.verify.forbid_patterns),
            )
        )
        steps.append(timed("smoke", lambda: step_smoke(wt, root, cfg.verify.smoke)))
    finally:
        run(["git", "worktree", "remove", "--force", str(wt)], root)
        run(["git", "worktree", "prune"], root)
        shutil.rmtree(tmp, ignore_errors=True)


def ensure_gh(root: Path) -> None:
    if not shutil.which("gh"):
        raise VerifyError(
            "GitHub CLI `gh` is not installed: https://cli.github.com (or use --local BRANCH)"
        )
    if run(["gh", "auth", "status"], root, timeout=30).returncode != 0:
        raise VerifyError("gh is not logged in: run `gh auth login` (or use --local BRANCH)")


def verify_pr(root: Path, number: int, cfg: hackkit_config.Config) -> tuple[list[Step], str]:
    ensure_gh(root)
    proc = run(["gh", "pr", "view", str(number), "--json", PR_FIELDS], root, timeout=60)
    if proc.returncode != 0:
        raise VerifyError(f"gh pr view {number} failed: {tail(proc.stderr)}")
    pr = json.loads(proc.stdout)
    base = cfg.verify.base_branch
    steps = [check_state(pr), check_base(pr, base)]
    start = time.monotonic()
    git(root, "fetch", "--quiet", "origin", base)
    git(root, "fetch", "--quiet", "origin", f"pull/{number}/head")
    head = git(root, "rev-parse", "FETCH_HEAD")
    note = f"head {head[:9]}"
    if pr.get("headRefOid") and pr["headRefOid"] != head:
        note += f" (GitHub says {pr['headRefOid'][:9]}: pushed meanwhile?)"
    steps.append(Step("fetch", PASS, time.monotonic() - start, note))
    verify_merge(root, f"origin/{base}", head, cfg, steps)
    return steps, f"PR #{number}: {pr.get('title', '')} ({pr.get('headRefName')} -> {base})"


def default_base_ref(root: Path, base: str) -> str:
    remote = f"refs/remotes/origin/{base}"
    if run(["git", "show-ref", "--verify", "--quiet", remote], root).returncode == 0:
        return f"origin/{base}"
    return base


def verify_local(
    root: Path, branch: str, cfg: hackkit_config.Config, base_ref: str | None = None
) -> tuple[list[Step], str]:
    """Verify a local branch against the base without gh or network."""
    base_ref = base_ref or default_base_ref(root, cfg.verify.base_branch)
    for ref in (branch, base_ref):
        if run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], root).returncode:
            raise VerifyError(f"unknown branch or ref {ref!r} (see `git branch -a`)")
    head = git(root, "rev-parse", f"{branch}^{{commit}}")
    steps = [Step("target branch", SKIP, note=f"local mode: merging into {base_ref}")]
    verify_merge(root, base_ref, head, cfg, steps)
    return steps, f"branch {branch} ({head[:9]}) -> {base_ref}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pr", nargs="?", type=int, help="pull request number")
    ap.add_argument("--local", metavar="BRANCH", help="verify a local branch (no gh)")
    ap.add_argument("--base-ref", help="with --local: ref to merge into (default origin/<base>)")
    ap.add_argument("--comment", action="store_true", help="post the report on the PR")
    ap.add_argument("--repo", type=Path, help="repo (default: the repo of the cwd)")
    args = ap.parse_args(argv)
    if (args.pr is None) == (args.local is None):
        ap.error("give a PR number or --local BRANCH (make verify PR=12 | BRANCH=agent/x)")

    root = hackkit_config.repo_root(args.repo or Path.cwd())
    cfg = hackkit_config.load_config(root)
    try:
        if args.local:
            steps, title = verify_local(root, args.local, cfg, args.base_ref)
        else:
            steps, title = verify_pr(root, args.pr, cfg)
    except VerifyError as err:
        print(f"verify: {err}", file=sys.stderr)
        return 2

    report = render_summary(steps, f"verify {title}")
    print(report)
    if args.comment and args.pr is not None:
        body = report + "\n\n<sub>posted by `make verify` (scripts/verify_pr.py)</sub>"
        proc = subprocess.run(
            ["gh", "pr", "comment", str(args.pr), "--body-file", "-"],
            input=body,
            text=True,
            capture_output=True,
            cwd=root,
            check=False,
        )
        print("comment posted" if proc.returncode == 0 else f"comment failed: {tail(proc.stderr)}")
    return 0 if problems(steps) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
