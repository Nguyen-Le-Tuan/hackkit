"""scripts/verify_pr.py: pure logic, plus --local mode on a throw-away repo (no gh, no network)."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import hackkit_config  # noqa: E402
import verify_pr as vp  # noqa: E402

DIFF = """\
diff --git a/src/app.py b/src/app.py
index 1111111..2222222 100644
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
 import os
-OWNER = "x"
+OWNER = "Acme Corp"
+print("ok")
 done = True
@@ -10,2 +11,3 @@ def f():
     pass
+    # acme corp internal
diff --git a/docs/new.md b/docs/new.md
new file mode 100644
--- /dev/null
+++ b/docs/new.md
@@ -0,0 +1 @@
+hello
"""


def test_check_base_passes_on_main_and_explains_the_fix_otherwise():
    assert vp.check_base({"number": 7, "baseRefName": "main"}, "main").result == vp.PASS
    step = vp.check_base({"number": 7, "baseRefName": "feat/pr1"}, "main")
    assert step.result == vp.FAIL
    assert "targets 'feat/pr1', not main" in step.note
    assert "gh pr edit 7 --base main" in step.note


def test_check_state_flags_closed_prs_and_notes_forks():
    open_pr = {"state": "OPEN", "files": [{}, {}], "headRefName": "agent/a"}
    assert vp.check_state(open_pr).result == vp.PASS
    closed = vp.check_state({"state": "CLOSED", "isCrossRepository": True})
    assert closed.result == vp.FAIL and "fork" in closed.note


def test_added_lines_tracks_files_and_line_numbers():
    added = vp.added_lines(DIFF)
    assert added == [
        ("src/app.py", 2, 'OWNER = "Acme Corp"'),
        ("src/app.py", 3, 'print("ok")'),
        ("src/app.py", 12, "    # acme corp internal"),
        ("docs/new.md", 1, "hello"),
    ]


def test_find_forbidden_reports_location_not_text():
    hits = vp.find_forbidden(DIFF, ["(?i)acme corp", "x = 1"])
    assert hits == [
        "src/app.py:2 matches /(?i)acme corp/",
        "src/app.py:12 matches /(?i)acme corp/",
    ]
    assert vp.find_forbidden(DIFF, ['OWNER = "x"']) == []  # removed lines do not count
    assert vp.find_forbidden(DIFF, ["(unclosed"]) == []  # a bad regex is reported, not fatal


def test_render_summary_and_verdict():
    steps = [
        vp.Step("target branch", vp.FAIL, 0.0, "targets 'a|b', not main"),
        vp.Step("pytest", vp.PASS, 2.345, "38 passed"),
        vp.Step("smoke", vp.SKIP, 0.0, "no server"),
    ]
    text = vp.render_summary(steps, "verify PR #3")
    assert text.startswith("### verify PR #3\n\n| step | result | time | note |")
    assert "| pytest | PASS | 2.3s | 38 passed |" in text
    assert "a\\|b" in text  # pipes are escaped inside cells
    assert text.endswith("VERDICT: DO NOT MERGE (1 problems)")
    assert vp.verdict(steps[1:]) == "VERDICT: MERGE OK"


def git(repo: Path, *args: str) -> str:
    ident = ["-c", "user.email=t@t", "-c", "user.name=t", "-c", "core.hooksPath=/dev/null"]
    return subprocess.run(
        ["git", *ident, *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "hackkit.toml").write_text('[verify]\nforbid_patterns = ["(?i)acme"]\nsmoke = false\n')
    (root / "notes.txt").write_text("line one\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    git(root, "switch", "-q", "-c", "agent/ok")
    (root / "feature.txt").write_text("a new feature\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "feature")
    git(root, "switch", "-q", "-c", "agent/bad", "main")
    (root / "notes.txt").write_text("line one for ACME\n")
    (root / "costs.xlsx").write_bytes(b"PK\x03\x04")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "bad")
    git(root, "switch", "-q", "main")
    (root / "notes.txt").write_text("line one, edited on main\n")
    git(root, "commit", "-q", "-am", "main moves on")
    return root


def results(steps: list) -> dict[str, str]:
    return {s.name: s.result for s in steps}


def test_local_clean_branch_is_merge_ok(repo):
    cfg = hackkit_config.load_config(repo)
    steps, title = vp.verify_local(repo, "agent/ok", cfg)
    r = results(steps)
    assert r["merge"] == vp.PASS and r["guard"] == vp.PASS and r["forbidden"] == vp.PASS
    assert r["smoke"] == vp.SKIP and r["pytest"] == vp.SKIP  # no tests in the toy repo
    assert vp.problems(steps) == 0, vp.render_summary(steps, title)
    assert "agent/ok" in title and "-> main" in title
    assert git(repo, "worktree", "list").count("\n") == 0  # temp worktree removed


def test_local_conflicting_branch_fails_at_merge_and_cleans_up(repo, capsys):
    code = vp.main(["--local", "agent/bad", "--repo", str(repo)])
    out = capsys.readouterr().out
    assert code == 1
    assert "| merge | FAIL |" in out and "conflicts in notes.txt" in out
    assert "VERDICT: DO NOT MERGE (1 problems)" in out
    assert git(repo, "worktree", "list").count("\n") == 0
    assert git(repo, "status", "--porcelain") == ""


def test_local_guard_and_forbidden_failures(repo):
    git(repo, "switch", "-q", "agent/bad")
    git(repo, "merge", "-q", "-X", "ours", "main", "-m", "sync")  # keep the branch side
    git(repo, "switch", "-q", "main")
    steps, _ = vp.verify_local(repo, "agent/bad", hackkit_config.load_config(repo))
    r = results(steps)
    assert r["merge"] == vp.PASS
    assert r["guard"] == vp.FAIL and r["forbidden"] == vp.FAIL
    note = next(s.note for s in steps if s.name == "forbidden")
    assert "notes.txt:1 matches /(?i)acme/" in note and "ACME" not in note


def test_unknown_branch_is_a_usage_error(repo, capsys):
    assert vp.main(["--local", "nope", "--repo", str(repo)]) == 2
    assert "unknown branch" in capsys.readouterr().err


def test_pytest_summary_reads_both_quiet_levels():
    assert vp.pytest_summary("..\n===== 2 passed in 0.1s =====\n") == "2 passed in 0.1s"
    assert vp.pytest_summary("." * 72 + " [ 62%]\n" + "." * 44 + " [100%]\n") == "116 passed"
