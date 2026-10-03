"""scripts/guard.py and scripts/hackkit_config.py on throw-away git repos."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import guard  # noqa: E402
import hackkit_config  # noqa: E402

FAKE_KEY = "gsk_" + "A1b2C3d4E5f6G7h8I9j0K1l2"  # not a real key


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "README.md").write_text("# demo\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def write(repo: Path, rel: str, data: bytes | str = "x\n") -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data)
    else:
        path.write_bytes(data)
    return path


def stage(repo: Path, *rels: str) -> None:
    git(repo, "add", "-f", "--", *rels)


def checks(result: guard.GuardResult) -> set[str]:
    return {f.check for f in result.problems}


# --------------------------------------------------------------------------- config


def test_config_defaults_when_file_missing(tmp_path):
    cfg = hackkit_config.load_config(tmp_path)
    assert cfg.path is None
    assert ".xlsx" in cfg.guard.blocked_extensions and cfg.guard.max_file_mb == 5
    assert "tests/fixtures/**" in cfg.guard.allow
    assert "**/node_modules/**" in cfg.guard.blocked_paths
    assert cfg.verify.base_branch == "main" and cfg.verify.forbid_patterns == []
    assert cfg.verify.smoke is True and cfg.freeze.label == "bugfix"


def test_config_partial_file_keeps_other_defaults(tmp_path, capsys):
    (tmp_path / "hackkit.toml").write_text(
        '[guard]\nmax_file_mb = 1.5\nblocked_extensions = ["CSV"]\nallow = "oops"\n'
        '[verify]\nforbid_patterns = ["(?i)acme"]\n'
    )
    cfg = hackkit_config.load_config(tmp_path)
    assert cfg.guard.max_file_mb == 1.5
    assert cfg.guard.blocked_extensions == [".csv"]  # normalized
    assert cfg.guard.allow == hackkit_config.DEFAULT_ALLOW  # wrong type -> default
    assert "[guard].allow has the wrong type" in capsys.readouterr().err
    assert cfg.verify.forbid_patterns == ["(?i)acme"] and cfg.verify.base_branch == "main"
    assert cfg.freeze.label == "bugfix"


def test_config_invalid_toml_falls_back_to_defaults(tmp_path):
    (tmp_path / "hackkit.toml").write_text("[guard\nnot toml")
    assert hackkit_config.load_config(tmp_path).guard.max_file_mb == 5


def test_repo_config_file_parses():
    cfg = hackkit_config.load_config(SCRIPTS.parent)
    assert cfg.path is not None and cfg.verify.base_branch == "main"


# --------------------------------------------------------------------------- matching


@pytest.mark.parametrize(
    ("path", "pattern", "expected"),
    [
        ("node_modules/x.js", "**/node_modules/**", True),
        ("web/node_modules", "**/node_modules/**", True),  # the symlink itself
        ("web/node_modules_old/x", "**/node_modules/**", False),
        ("partner/a/b.xlsx", "partner/**", True),
        ("docs/partner/b.xlsx", "partner/**", False),
        (".env", "**/.env", True),
        ("app/.env.local", "**/.env.*", True),
        ("tests/fixtures/a/b.pdf", "tests/fixtures/**", True),
        ("src/a.py", "src/*.py", True),
        ("src/x/a.py", "src/*.py", False),
    ],
)
def test_glob_match(path, pattern, expected):
    assert guard.glob_match(path, pattern) is expected


def test_negated_blocked_path_reallows_env_example():
    patterns = hackkit_config.DEFAULT_BLOCKED_PATHS
    assert guard.blocked_path_pattern(".env.example", patterns) is None
    assert guard.blocked_path_pattern(".env.production", patterns) == "**/.env.*"


@pytest.mark.parametrize(
    ("link", "target", "escapes"),
    [
        ("a/link", "../README.md", False),
        ("link", "docs/x", False),
        ("link", "../outside", True),
        ("a/b/link", "../../../x", True),
        ("node_modules", "/home/user/node_modules", True),
        ("x", "~/stuff", True),
    ],
)
def test_symlink_escapes(link, target, escapes):
    assert guard.symlink_escapes(link, target) is escapes


# --------------------------------------------------------------------------- problem classes


def test_clean_staged_change_passes(repo):
    write(repo, "src/app.py", "print('hi')\n")
    write(repo, ".env.example", "GROQ_API_KEY=\n")
    stage(repo, "src/app.py", ".env.example")
    result = guard.run_guard(repo, "staged")
    assert result.ok and result.checked == 2


def test_blocked_extension_outside_allow_fails(repo):
    write(repo, "data/partner_costs.xlsx", b"PK\x03\x04fake")
    stage(repo, "data/partner_costs.xlsx")
    result = guard.run_guard(repo, "staged")
    assert checks(result) == {"blocked-ext"}
    assert "[guard].allow" in result.problems[0].message


def test_blocked_extension_inside_allow_passes(repo):
    write(repo, "tests/fixtures/sample.xlsx", b"PK\x03\x04fake")
    write(repo, "docs/pitch/assets/deck.pdf", b"%PDF-1.4")
    stage(repo, "tests/fixtures/sample.xlsx", "docs/pitch/assets/deck.pdf")
    assert guard.run_guard(repo, "staged").ok


def test_big_file_fails(repo):
    write(repo, "hackkit.toml", "[guard]\nmax_file_mb = 0.01\n")
    write(repo, "assets/big.png", os.urandom(20_000))
    stage(repo, "hackkit.toml", "assets/big.png")
    result = guard.run_guard(repo, "staged")
    assert checks(result) == {"size"}
    assert result.problems[0].path == "assets/big.png"


def test_gitlink_without_gitmodules_fails_and_registered_submodule_passes(repo):
    sha = "1234567890abcdef1234567890abcdef12345678"
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{sha},AI_agent")
    result = guard.run_guard(repo, "staged")
    assert checks(result) == {"gitlink"}
    assert "git rm --cached AI_agent" in result.problems[0].message

    write(repo, ".gitmodules", '[submodule "AI_agent"]\n\tpath = AI_agent\n\turl = ../x\n')
    stage(repo, ".gitmodules")
    assert guard.run_guard(repo, "staged").ok


def test_escaping_symlinks_fail_and_inner_symlink_passes(repo):
    os.symlink("../../outside", repo / "escape")
    os.symlink("/etc/hostname", repo / "absolute")
    write(repo, "docs/x.md")
    os.symlink("../README.md", repo / "docs" / "readme")
    stage(repo, "escape", "absolute", "docs/x.md", "docs/readme")
    result = guard.run_guard(repo, "staged")
    assert checks(result) == {"symlink"}
    assert sorted(f.path for f in result.problems) == ["absolute", "escape"]


def test_node_modules_symlink_and_files_fail(repo):
    os.symlink("/home/someone/node_modules", repo / "node_modules")
    write(repo, "web/node_modules/lib/index.js", "module.exports = 1\n")
    stage(repo, "node_modules", "web/node_modules/lib/index.js")
    result = guard.run_guard(repo, "staged")
    paths = {(f.check, f.path) for f in result.problems}
    assert ("blocked-path", "node_modules") in paths
    assert ("symlink", "node_modules") in paths
    assert ("blocked-path", "web/node_modules/lib/index.js") in paths


def test_env_and_partner_files_fail(repo):
    write(repo, ".env", "LLM_PROVIDER=fake\n")
    write(repo, "app/.env.local", "X=1\n")
    write(repo, "partner/notes.md", "confidential\n")
    stage(repo, ".env", "app/.env.local", "partner/notes.md")
    result = guard.run_guard(repo, "staged")
    assert {f.path for f in result.problems} == {".env", "app/.env.local", "partner/notes.md"}
    assert checks(result) == {"blocked-path"}


def test_secret_is_found_but_never_printed(repo, capsys, monkeypatch):
    write(repo, "docs/BRIEF.md", f"line\nkey = {FAKE_KEY}\n")
    stage(repo, "docs/BRIEF.md")
    monkeypatch.chdir(repo)
    assert guard.main(["--staged"]) == 1
    out = capsys.readouterr().out
    assert "FAIL [secret] docs/BRIEF.md:2" in out and "Groq key" in out
    assert FAKE_KEY not in out


def test_env_value_is_found_but_never_printed(repo, tmp_path, capsys):
    env = write(tmp_path, "secrets.env", "MY_TOKEN=correct-horse-battery\n")
    write(repo, "notes.md", "the token is correct-horse-battery\n")
    stage(repo, "notes.md")
    assert guard.main(["--staged", "--repo", str(repo), "--env", str(env)]) == 1
    out = capsys.readouterr().out
    assert "value of MY_TOKEN from .env" in out and "correct-horse-battery" not in out


def test_duplicate_binaries_warn_only(repo):
    blob = os.urandom(60_000)
    for i in range(3):
        write(repo, f"img/shot{i}.png", blob)
    stage(repo, "img")
    result = guard.run_guard(repo, "staged")
    assert result.ok
    assert [w.check for w in result.warnings] == ["duplicate"]
    assert "3 identical copies" in result.warnings[0].message


def test_all_mode_sees_committed_files_staged_mode_does_not(repo):
    write(repo, "report.docx", b"PK\x03\x04")
    stage(repo, "report.docx")
    git(repo, "commit", "-q", "-m", "oops")
    write(repo, "ok.py", "x = 1\n")
    stage(repo, "ok.py")
    assert guard.run_guard(repo, "staged").ok
    assert checks(guard.run_guard(repo, "all")) == {"blocked-ext"}


def test_main_works_from_a_subfolder(repo, monkeypatch, capsys):
    write(repo, "sub/deep/file.txt")
    stage(repo, "sub/deep/file.txt")
    monkeypatch.chdir(repo / "sub" / "deep")
    assert guard.main(["--all"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_this_repo_passes_the_guard():
    assert guard.run_guard(SCRIPTS.parent, "all").ok


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_pre_commit_hook_blocks_an_xlsx_commit(repo):
    for name in ("guard.py", "hackkit_config.py", "secret_scan.py", "hooks/pre-commit"):
        dest = repo / "scripts" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPTS / name, dest)
    git(repo, "add", "scripts")
    git(repo, "commit", "-q", "-m", "guard")
    write(repo, "NOCO costs.xlsx", b"PK\x03\x04")
    stage(repo, "NOCO costs.xlsx")
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "core.hooksPath=scripts/hooks"]
        + ["commit", "-q", "-m", "add partner sheet"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "FAIL [blocked-ext] NOCO costs.xlsx" in proc.stdout + proc.stderr
