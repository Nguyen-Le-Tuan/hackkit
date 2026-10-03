import importlib.util
import subprocess
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "secret_scan", Path(__file__).resolve().parents[1] / "scripts" / "secret_scan.py"
)
scan = importlib.util.module_from_spec(_SPEC)
sys.modules["secret_scan"] = scan
_SPEC.loader.exec_module(scan)

FAKE_KEY = "gsk_" + "A1b2C3d4E5f6G7h8I9j0K1l2"  # not a real key


def write_env(tmp_path, body):
    env = tmp_path / ".env"
    env.write_text(body, encoding="utf-8")
    return env


def test_check_env_flags_filled_secrets_and_ignores_the_rest(tmp_path, capsys):
    env = write_env(
        tmp_path,
        f"# comment\nLLM_PROVIDER=groq\nGROQ_MODEL=openai/gpt-oss-120b\nGROQ_API_KEY={FAKE_KEY}\n"
        "ANTHROPIC_API_KEY=\nOLLAMA_URL=http://localhost:11434\n",
    )
    assert scan.main(["--check-env", "--env", str(env)]) == 1
    out = capsys.readouterr().out
    assert "FILLED: GROQ_API_KEY" in out and FAKE_KEY not in out
    assert "ANTHROPIC_API_KEY" not in out  # empty values are fine
    empty = write_env(tmp_path, "GROQ_API_KEY=\nLLM_PROVIDER=fake\n")
    assert scan.main(["--check-env", "--env", str(empty)]) == 0
    assert scan.main(["--check-env", "--env", str(tmp_path / "missing")]) == 0


def test_scan_finds_the_env_value_and_known_formats_without_printing_them(tmp_path, capsys):
    env = write_env(tmp_path, "MY_SECRET_THING=correct-horse-battery\n")
    doc = tmp_path / "BRIEF.md"
    doc.write_text(
        f"fine line\nthe token is correct-horse-battery ok\nkey {FAKE_KEY}\nsk-" + "x" * 30 + "\n",
        encoding="utf-8",
    )
    assert scan.main(["--env", str(env), str(doc)]) == 1
    out = capsys.readouterr().out
    assert "value of MY_SECRET_THING from .env in" in out and "BRIEF.md:2" in out
    assert "Groq key" in out and "OpenAI/Anthropic-style key" in out
    assert "correct-horse-battery" not in out and FAKE_KEY not in out


def test_clean_files_pass(tmp_path, capsys):
    doc = tmp_path / "PLANS.md"
    doc.write_text("# Plans\nUse GROQ_API_KEY from .env. No secrets here.\n", encoding="utf-8")
    assert scan.main(["--env", str(tmp_path / ".env"), str(doc)]) == 0
    assert "clean (1 file(s) scanned)" in capsys.readouterr().out


def test_repo_mode_scans_only_changed_and_untracked_files(tmp_path, capsys):
    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    old = tmp_path / "old.md"
    old.write_text(f"{FAKE_KEY}\n", encoding="utf-8")  # already in history: not "changed"
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "BRIEF.md").write_text(f"leaked: {FAKE_KEY}\n", encoding="utf-8")
    (tmp_path / "docs" / "other.md").write_text("harmless\n", encoding="utf-8")
    code = scan.main(["--repo", str(tmp_path), "--since", "HEAD"])
    out = capsys.readouterr().out
    assert code == 1 and "docs/BRIEF.md:1" in out and "old.md" not in out
