"""scripts/freeze.py: the CI rule (check_pr) and freeze/unfreeze on a throw-away repo."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import freeze  # noqa: E402
import hackkit_config  # noqa: E402

FROZEN = json.dumps({"frozen_at": "2026-10-03T14:00:00+07:00", "by": "Tuan", "label": "bugfix"})
FROZEN_HOTFIX = json.dumps({"frozen_at": "2026-10-03T14:00:00+07:00", "label": "hotfix"})


@pytest.mark.parametrize(
    ("labels", "text", "ok"),
    [
        ([], None, True),  # no .freeze on the base branch
        (["bugfix"], None, True),
        ([], FROZEN, False),
        (["feature", "ui"], FROZEN, False),
        (["bugfix"], FROZEN, True),
        (["BugFix "], FROZEN, True),  # case and whitespace do not matter
        (["bugfix"], FROZEN_HOTFIX, False),  # the label stored in .freeze wins
        (["hotfix"], FROZEN_HOTFIX, True),
        ([], "not json", False),  # an unreadable .freeze still freezes
        (["bugfix"], "not json", True),
        ([], "", False),
    ],
)
def test_check_pr_truth_table(labels, text, ok):
    allowed, message = freeze.check_pr(labels, text, "bugfix")
    assert allowed is ok
    if not ok:
        assert "demo freeze" in message and "--add-label" in message


def test_check_pr_uses_configured_label_when_file_has_none():
    assert freeze.check_pr(["qa-ok"], "{}", "qa-ok")[0] is True
    assert freeze.check_pr(["bugfix"], "{}", "qa-ok")[0] is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('["bugfix", "ui"]', ["bugfix", "ui"]),
        ("[]", []),
        ("", []),
        ("bugfix, ui", ["bugfix", "ui"]),
        ('"bugfix"', ["bugfix"]),
    ],
)
def test_parse_labels(raw, expected):
    assert freeze.parse_labels(raw) == expected


def test_check_command_reads_the_freeze_file(tmp_path, capsys):
    frozen = tmp_path / "base.freeze"
    frozen.write_text(FROZEN)
    assert freeze.main(["check", "--labels", "[]", "--freeze-file", str(frozen)]) == 1
    assert "freeze-check: FAIL" in capsys.readouterr().out
    assert freeze.main(["check", "--labels", '["bugfix"]', "--freeze-file", str(frozen)]) == 0
    missing = tmp_path / "absent"
    assert freeze.main(["check", "--labels", "[]", "--freeze-file", str(missing)]) == 0


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "Tester")
    git(root, "config", "core.hooksPath", "/dev/null")
    (root / "README.md").write_text("x\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def test_freeze_and_unfreeze_commit_the_file(repo, capsys):
    cfg = hackkit_config.load_config(repo)
    (repo / "wip.py").write_text("x = 1\n")
    git(repo, "add", "wip.py")  # staged work must not ride along in the freeze commit

    assert freeze.cmd_freeze(repo, cfg, protect=False) == 0
    out = capsys.readouterr().out
    assert "FROZEN" in out and "git push origin main" in out
    info = json.loads((repo / ".freeze").read_text())
    assert info["by"] == "Tester" and info["label"] == "bugfix" and info["frozen_at"]
    assert git(repo, "log", "-1", "--format=%s") == "chore: demo freeze"
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == ".freeze"
    assert freeze.check_pr([], git(repo, "show", "HEAD:.freeze"))[0] is False

    assert freeze.cmd_freeze(repo, cfg, protect=False) == 0
    assert "already frozen" in capsys.readouterr().out

    assert freeze.cmd_status(repo, cfg) == 0
    assert "FROZEN since" in capsys.readouterr().out

    assert freeze.cmd_unfreeze(repo, cfg) == 0
    assert not (repo / ".freeze").exists()
    assert git(repo, "log", "-1", "--format=%s") == "chore: demo unfreeze"
    assert "git push origin main" in capsys.readouterr().out


def test_freeze_refuses_another_branch(repo, capsys):
    git(repo, "switch", "-q", "-c", "feature/x")
    cfg = hackkit_config.load_config(repo)
    assert freeze.cmd_freeze(repo, cfg, protect=False) == 1
    assert "must land on main" in capsys.readouterr().out
    assert not (repo / ".freeze").exists()


def test_visibility_falls_back_to_the_rest_api_on_old_gh(monkeypatch, tmp_path):
    """gh < 2.50 rejects --accept-visibility-change-consequences; the API call still works."""
    import subprocess
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import visibility

    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        if cmd[:3] == ["gh", "repo", "edit"]:
            return subprocess.CompletedProcess(cmd, 1, "", "unknown flag")
        if cmd[:3] == ["gh", "repo", "view"]:
            return subprocess.CompletedProcess(cmd, 0, "me/app\n", "")
        return subprocess.CompletedProcess(cmd, 0, "private\n", "")

    monkeypatch.setattr(visibility.subprocess, "run", fake_run)
    assert visibility.set_visibility(tmp_path, "private") == 0
    assert calls[-1][:5] == ["gh", "api", "-X", "PATCH", "repos/me/app"]
