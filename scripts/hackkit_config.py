"""Load `hackkit.toml` (the machine-enforced rules) with defaults. Standard library only.

    from hackkit_config import load_config, repo_root
    cfg = load_config(repo_root())
    cfg.guard.max_file_mb, cfg.verify.base_branch, cfg.freeze.label

A missing file, a missing section or a missing key falls back to the defaults below; a key with
the wrong type also falls back (with a warning on stderr) so a typo never disables a guard.
Run it directly to print the effective configuration: `python scripts/hackkit_config.py`.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

CONFIG_NAME = "hackkit.toml"

DEFAULT_BLOCKED_EXTENSIONS = [
    ".xlsx", ".xls", ".xlsm", ".docx", ".doc", ".pptx", ".ppt", ".pdf", ".key", ".numbers",
    ".pages", ".zip", ".7z", ".rar", ".mp4", ".mov", ".webm", ".sqlite", ".db",
]  # fmt: skip
DEFAULT_ALLOW = ["docs/pitch/assets/**", "web/assets/**", "tests/fixtures/**"]
DEFAULT_BLOCKED_PATHS = [
    "**/node_modules/**",
    "partner/**",
    "**/.env",
    "**/.env.*",
    "!**/.env.example",
]


@dataclass
class GuardConfig:
    blocked_extensions: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCKED_EXTENSIONS))
    allow: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOW))
    max_file_mb: float = 5
    blocked_paths: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCKED_PATHS))


@dataclass
class VerifyConfig:
    base_branch: str = "main"
    forbid_patterns: list[str] = field(default_factory=list)
    smoke: bool = True


@dataclass
class FreezeConfig:
    label: str = "bugfix"


@dataclass
class Config:
    guard: GuardConfig = field(default_factory=GuardConfig)
    verify: VerifyConfig = field(default_factory=VerifyConfig)
    freeze: FreezeConfig = field(default_factory=FreezeConfig)
    path: Path | None = None  # the file that was read, or None when defaults are used


def _type_ok(default: Any, value: Any) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int | float):
        return isinstance(value, int | float) and not isinstance(value, bool)
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    return isinstance(value, type(default))


def _fill(section: Any, data: Any, name: str) -> Any:
    if not isinstance(data, dict):
        return section
    for f in fields(section):
        if f.name not in data:
            continue
        value = data[f.name]
        if _type_ok(getattr(section, f.name), value):
            setattr(section, f.name, value)
        else:
            print(
                f"hackkit.toml: [{name}].{f.name} has the wrong type; using the default",
                file=sys.stderr,
            )
    return section


def load_config(root: Path | str | None = None) -> Config:
    """Read `<root>/hackkit.toml` (root defaults to the current repo) merged over the defaults."""
    path = Path(root or repo_root()) / CONFIG_NAME
    cfg = Config()
    if not path.is_file():
        return cfg
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as err:
        print(f"hackkit.toml: cannot read it ({err}); using the defaults", file=sys.stderr)
        return cfg
    _fill(cfg.guard, data.get("guard"), "guard")
    _fill(cfg.verify, data.get("verify"), "verify")
    _fill(cfg.freeze, data.get("freeze"), "freeze")
    cfg.guard.blocked_extensions = [
        e.lower() if e.startswith(".") else f".{e.lower()}" for e in cfg.guard.blocked_extensions
    ]
    cfg.path = path
    return cfg


def repo_root(start: Path | str | None = None) -> Path:
    """Top level of the git work tree containing `start` (default: cwd).

    When git is missing or `start` is not inside a repo, returns `start` itself (or, without
    `start`, the folder above scripts/).
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start or Path.cwd(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if out:
            return Path(out)
    except (OSError, subprocess.CalledProcessError):
        pass
    return Path(start).resolve() if start else Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    loaded = load_config()
    print(f"# from {loaded.path or 'built-in defaults'}")
    for section in (loaded.guard, loaded.verify, loaded.freeze):
        for f in fields(section):
            print(f"{type(section).__name__}.{f.name} = {getattr(section, f.name)!r}")
