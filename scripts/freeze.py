#!/usr/bin/env python3
"""Demo freeze: after the freeze, only labeled bug-fix PRs may merge.

    python scripts/freeze.py freeze      # make freeze: write + commit .freeze, protect the branch
    python scripts/freeze.py unfreeze    # make unfreeze: remove + commit .freeze
    python scripts/freeze.py status      # make freeze-status
    python scripts/freeze.py check --labels '["bugfix"]' --freeze-file PATH   # used by CI

The freeze is a committed file, `.freeze` (JSON: frozen_at, by, label), at the repo root of the
base branch. CI's `freeze-check` job fails every pull request into a frozen base branch unless
the PR carries the [freeze].label from hackkit.toml (default "bugfix"). The time is the file's
commit, so nobody can quietly move it. `freeze` also tries to turn on GitHub branch protection
(required checks: test, freeze-check); this needs admin rights and may be unavailable on free
private repos, in which case it says why and continues. Nothing is pushed automatically.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hackkit_config  # noqa: E402

FREEZE_FILE = ".freeze"
REQUIRED_CHECKS = ["test", "freeze-check"]


# --------------------------------------------------------------------------- pure logic


def parse_freeze(text: str | None) -> dict | None:
    """The .freeze content as a dict; None when not frozen. Unreadable content still freezes."""
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def check_pr(
    labels: list[str], freeze_file_text: str | None, default_label: str = "bugfix"
) -> tuple[bool, str]:
    """May a PR merge? `freeze_file_text` is the base branch's .freeze (None = no file)."""
    info = parse_freeze(freeze_file_text)
    if info is None:
        return True, "not frozen: any PR may merge"
    label = str(info.get("label") or default_label)
    since = info.get("frozen_at", "unknown time")
    if label.lower() in {str(lb).strip().lower() for lb in labels}:
        return True, f"frozen since {since}, but the PR carries the {label!r} label"
    return False, (
        f"the base branch is in demo freeze (since {since}, by {info.get('by', '?')}): only "
        f"PRs labeled {label!r} may merge. If this is a demo-breaking bug fix, add the label "
        f"(`gh pr edit <N> --add-label {label}`) and re-run the job; otherwise wait for "
        "`make unfreeze` after the demo"
    )


def parse_labels(raw: str) -> list[str]:
    """Labels from CI: a JSON list (toJson output) or a comma-separated string."""
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(data, list):
        return [str(x) for x in data]
    return [str(data)]


# --------------------------------------------------------------------------- git / gh helpers


def run(cmd: list[str], cwd: Path, data: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=cwd, input=data, capture_output=True, text=True, timeout=60, check=False
    )


def git_out(root: Path, *args: str) -> str:
    proc = run(["git", *args], root)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def commit_freeze_change(root: Path, message: str) -> bool:
    proc = run(["git", "commit", "--quiet", "-m", message, "--", FREEZE_FILE], root)
    if proc.returncode != 0:
        print(f"freeze: git commit failed: {(proc.stderr or proc.stdout).strip()}")
        return False
    return True


def protect_branch(root: Path, base: str, label: str) -> None:
    """Best effort: require green CI (test + freeze-check) on the base branch."""
    if not shutil.which("gh"):
        print("branch protection: skipped (GitHub CLI `gh` not installed)")
        return
    repo = run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], root)
    if repo.returncode != 0 or not repo.stdout.strip():
        print(f"branch protection: skipped (cannot read the repo: {repo.stderr.strip()[:200]})")
        return
    body = {
        "required_status_checks": {"strict": False, "contexts": REQUIRED_CHECKS},
        "enforce_admins": False,
        "required_pull_request_reviews": None,
        "restrictions": None,
    }
    endpoint = f"repos/{repo.stdout.strip()}/branches/{base}/protection"
    proc = run(["gh", "api", "-X", "PUT", endpoint, "--input", "-"], root, json.dumps(body))
    if proc.returncode == 0:
        print(f"branch protection: ON for {base} (required checks: {', '.join(REQUIRED_CHECKS)})")
    else:
        reason = (proc.stderr or proc.stdout).strip().splitlines()
        print(
            f"branch protection: NOT set ({reason[-1][:200] if reason else 'unknown error'}). "
            "It needs admin rights and GitHub Pro/Team for private repos; the CI freeze-check "
            "job still fails unlabeled PRs, so tell the integrator not to merge red PRs."
        )
    created = run(["gh", "label", "create", label, "--color", "d73a4a", "--force"], root)
    if created.returncode == 0:
        print(f"label {label!r} is ready on GitHub")


# --------------------------------------------------------------------------- commands


def cmd_freeze(
    root: Path, cfg: hackkit_config.Config, allow_other_branch: bool = False, protect: bool = True
) -> int:
    base, label = cfg.verify.base_branch, cfg.freeze.label
    path = root / FREEZE_FILE
    if path.exists():
        print(f"already frozen: {path.read_text(encoding='utf-8').strip()}")
        return 0
    branch = git_out(root, "branch", "--show-current")
    if branch != base and not allow_other_branch:
        print(
            f"freeze: you are on {branch or 'a detached HEAD'!r}; the freeze must land on {base}. "
            f"Run `git switch {base} && git pull`, then `make freeze` again."
        )
        return 1
    info = {
        "frozen_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "by": git_out(root, "config", "user.name") or "unknown",
        "label": label,
    }
    path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    run(["git", "add", "--", FREEZE_FILE], root)
    if not commit_freeze_change(root, "chore: demo freeze"):
        return 1
    print(f"FROZEN at {info['frozen_at']} by {info['by']}: only PRs labeled {label!r} pass CI.")
    if protect:
        protect_branch(root, base, label)
    print(f"Now publish it: git push origin {base}")
    return 0


def cmd_unfreeze(root: Path, cfg: hackkit_config.Config) -> int:
    base = cfg.verify.base_branch
    path = root / FREEZE_FILE
    if not path.exists():
        print("not frozen: nothing to do")
        return 0
    tracked = run(["git", "ls-files", "--error-unmatch", FREEZE_FILE], root).returncode == 0
    if tracked:
        run(["git", "rm", "--quiet", "--", FREEZE_FILE], root)
        if not commit_freeze_change(root, "chore: demo unfreeze"):
            return 1
    else:
        path.unlink()
    print("UNFROZEN: any PR with green CI may merge again.")
    print("Branch protection (green CI required) stays on; change it in the repo settings.")
    print(f"Now publish it: git push origin {base}")
    return 0


def cmd_status(root: Path, cfg: hackkit_config.Config) -> int:
    base = cfg.verify.base_branch
    path = root / FREEZE_FILE
    local = path.read_text(encoding="utf-8") if path.exists() else None
    info = parse_freeze(local)
    if info is None:
        print("not frozen (no .freeze in this checkout)")
    else:
        print(
            f"FROZEN since {info.get('frozen_at', '?')} by {info.get('by', '?')}; "
            f"PRs need the {info.get('label') or cfg.freeze.label!r} label"
        )
    remote = run(["git", "show", f"origin/{base}:{FREEZE_FILE}"], root)
    if run(["git", "rev-parse", "--verify", "--quiet", f"origin/{base}"], root).returncode == 0:
        state = "frozen" if remote.returncode == 0 else "not frozen"
        print(f"origin/{base} (last fetch): {state}")
        if (remote.returncode == 0) != (info is not None):
            print(f"  -> differs from this checkout: push or pull {base}")
    return 0


def cmd_check(labels_raw: str, freeze_file: Path | None, cfg: hackkit_config.Config) -> int:
    text = None
    if freeze_file and freeze_file.is_file():
        text = freeze_file.read_text(encoding="utf-8")
    ok, message = check_pr(parse_labels(labels_raw), text, cfg.freeze.label)
    print(("freeze-check: OK - " if ok else "freeze-check: FAIL - ") + message)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    fr = sub.add_parser("freeze", help="freeze the base branch")
    fr.add_argument("--any-branch", action="store_true", help="allow freezing from another branch")
    fr.add_argument("--no-protect", action="store_true", help="skip the GitHub branch protection")
    sub.add_parser("unfreeze", help="lift the freeze")
    sub.add_parser("status", help="show the freeze state")
    ck = sub.add_parser("check", help="CI: may this PR merge?")
    ck.add_argument("--labels", default="", help="PR labels: JSON list or comma-separated")
    ck.add_argument("--freeze-file", type=Path, help="the base branch's .freeze (absent = none)")
    ap.add_argument("--repo", type=Path, help="repo (default: the repo of the cwd)")
    args = ap.parse_args(argv)

    root = hackkit_config.repo_root(args.repo or Path.cwd())
    cfg = hackkit_config.load_config(root)
    if args.command == "freeze":
        return cmd_freeze(root, cfg, args.any_branch, not args.no_protect)
    if args.command == "unfreeze":
        return cmd_unfreeze(root, cfg)
    if args.command == "status":
        return cmd_status(root, cfg)
    return cmd_check(args.labels, args.freeze_file, cfg)


if __name__ == "__main__":
    sys.exit(main())
