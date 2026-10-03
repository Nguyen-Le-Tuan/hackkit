#!/usr/bin/env python3
"""Demo-machine check: is THIS laptop ready to run the demo? (`make doctor`)

    python scripts/doctor.py

Prints one line per probe: OK / INFO / WARN / FAIL, what was found and how to fix it. Exit 1
only when something is FAIL (the demo cannot run); WARN means "fix it if you can". Every probe
is wrapped, so a missing tool is reported, never a crash. Key values from .env are never
printed: only whether each key is set or empty. Standard library only (python-dotenv is used
when installed).
"""

from __future__ import annotations

import argparse
import importlib.util
import platform
import re
import shutil
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hackkit_config  # noqa: E402

OK, INFO, WARN, FAIL = "OK", "INFO", "WARN", "FAIL"
PORT = 8000
KEY_NAMES = ("ANTHROPIC_API_KEY", "GROQ_API_KEY")
REQUIRED_IMPORTS = {"pydantic": "pydantic", "httpx": "httpx", "dotenv": "python-dotenv"}
OPTIONAL_IMPORTS = {
    "fastapi": "the web UI needs them: pip install -e .",
    "uvicorn": "the web UI needs them: pip install -e .",
    "playwright": (
        "make shots / demo-video need `pip install -e .[pitch]` and `playwright install chromium`"
    ),
    "pptx": "make deck needs python-pptx: pip install -e .[pitch]",
}


@dataclass
class Check:
    status: str
    name: str
    detail: str
    hint: str = ""


def run(cmd: list[str], cwd: Path | None = None, timeout: float = 5) -> str | None:
    """stdout of a command, or None when the tool is missing, fails or hangs."""
    if not shutil.which(cmd[0]):
        return None
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


# --------------------------------------------------------------------------- probes


def probe_python(root: Path) -> list[Check]:
    version = platform.python_version()
    checks = [
        Check(OK, "python", version)
        if sys.version_info >= (3, 11)
        else Check(FAIL, "python", version, "install Python 3.11+ and re-run make setup")
    ]
    in_venv = sys.prefix != sys.base_prefix
    repo_venv = (root / ".venv").resolve()
    if in_venv and Path(sys.prefix).resolve() == repo_venv:
        checks.append(Check(OK, "venv", ".venv of this repo"))
    elif in_venv:
        checks.append(
            Check(WARN, "venv", f"another venv: {sys.prefix}", "source .venv/bin/activate")
        )
    else:
        checks.append(
            Check(WARN, "venv", "not in a venv", "make setup, then source .venv/bin/activate")
        )
    return checks


def probe_imports(root: Path) -> list[Check]:
    checks = []
    for module, package in REQUIRED_IMPORTS.items():
        found = importlib.util.find_spec(module) is not None
        checks.append(
            Check(OK, f"import {module}", "installed")
            if found
            else Check(FAIL, f"import {module}", "missing", f"pip install -e . ({package})")
        )
    for module, hint in OPTIONAL_IMPORTS.items():
        found = importlib.util.find_spec(module) is not None
        checks.append(
            Check(OK, f"import {module}", "installed")
            if found
            else Check(WARN, f"import {module}", "missing", hint)
        )
    return checks


def read_env(path: Path) -> dict[str, str]:
    """Values of a .env file (python-dotenv when installed, else a simple parser)."""
    try:
        from dotenv import dotenv_values

        return {k: v or "" for k, v in dotenv_values(path).items()}
    except ImportError:
        values = {}
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and not name.startswith("#"):
                values[name.strip()] = value.strip().strip("'\"")
        return values


def probe_env(root: Path) -> list[Check]:
    path = root / ".env"
    if not path.is_file():
        return [
            Check(
                WARN,
                ".env",
                "missing (the fake provider will be used)",
                "cp .env.example .env and fill it in",
            )
        ]
    env = read_env(path)
    provider = (env.get("LLM_PROVIDER") or "fake").strip().lower()
    checks = [Check(OK, ".env", "present"), Check(INFO, "LLM_PROVIDER", provider)]
    for name in KEY_NAMES:
        state = "set" if (env.get(name) or "").strip() else "empty"
        needed = provider == name.split("_")[0].lower()
        if needed and state == "empty":
            checks.append(
                Check(WARN, name, state, f"LLM_PROVIDER={provider} needs it (or DEMO_MODE=true)")
            )
        else:
            checks.append(Check(OK if needed else INFO, name, state))
    demo = (env.get("DEMO_MODE") or "false").strip().lower()
    checks.append(
        Check(
            INFO,
            "DEMO_MODE",
            demo,
            ""
            if demo in {"1", "true", "yes", "on"}
            else "true = replay cache, no network on stage",
        )
    )
    return checks


def probe_git(root: Path) -> list[Check]:
    if run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root) is None:
        return [Check(WARN, "git", "not a git checkout (or git missing)", "clone the repo")]
    branch = (run(["git", "branch", "--show-current"], cwd=root) or "").strip()
    status = run(["git", "status", "--porcelain"], cwd=root) or ""
    dirty = len([ln for ln in status.splitlines() if ln.strip()])
    checks = [Check(INFO, "git branch", branch or "detached HEAD")]
    checks.append(
        Check(OK, "git changes", "clean")
        if not dirty
        else Check(WARN, "git changes", f"{dirty} uncommitted", "commit or stash before the demo")
    )
    if (root / ".freeze").exists():
        checks.append(Check(INFO, "freeze", "frozen (.freeze present)", "make freeze-status"))
    return checks


def probe_port(root: Path) -> list[Check]:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.3):
            busy = True
    except OSError:
        busy = False
    if not busy:
        return [Check(OK, f"port {PORT}", "free")]
    who = run(["ss", "-ltnp", f"sport = :{PORT}"]) or run(["lsof", "-iTCP:8000", "-sTCP:LISTEN"])
    users = re.findall(r'users:\(\("([^"]+)",pid=(\d+)', who or "")
    detail = ", ".join(f"{n} (pid {p})" for n, p in users) or "in use"
    return [Check(WARN, f"port {PORT}", detail, "stop the other server or use another port")]


def probe_tools(root: Path) -> list[Check]:
    checks = []
    node = run(["node", "--version"])
    checks.append(Check(INFO, "node", node.strip() if node else "not installed"))
    snapshot = root / "web" / "snapshots" / "index.json"
    checks.append(
        Check(OK, "offline snapshots", "web/snapshots/index.json")
        if snapshot.is_file()
        else Check(
            WARN,
            "offline snapshots",
            "web/snapshots/index.json missing",
            "run make snapshot so the static/offline demo works",
        )
    )
    for tool, why in (("soffice", "deck PDF export"), ("ffmpeg", "demo video mp4")):
        path = shutil.which(tool)
        checks.append(Check(INFO, tool, path or "not installed", "" if path else f"for {why}"))
    return checks


def probe_power(root: Path) -> list[Check]:
    supplies = Path("/sys/class/power_supply")
    if supplies.is_dir():
        on_ac, batteries = False, []
        for dev in supplies.iterdir():
            kind = (dev / "type").read_text().strip() if (dev / "type").is_file() else ""
            if kind == "Battery" and (dev / "status").is_file():
                batteries.append((dev / "status").read_text().strip())
            elif (dev / "online").is_file() and (dev / "online").read_text().strip() == "1":
                on_ac = True
        if batteries or on_ac:
            discharging = any(s.lower() == "discharging" for s in batteries)
            if discharging and not on_ac:
                return [Check(WARN, "power", "on battery", "plug the charger in for the demo")]
            return [Check(OK, "power", f"on AC ({', '.join(batteries) or 'no battery'})")]
    out = run(["pmset", "-g", "batt"])
    if out:
        if "Battery Power" in out:
            return [Check(WARN, "power", "on battery", "plug the charger in for the demo")]
        return [Check(OK, "power", "on AC")]
    out = run(["upower", "-i", "/org/freedesktop/UPower/devices/DisplayDevice"])
    if out and re.search(r"state:\s+discharging", out):
        return [Check(WARN, "power", "on battery", "plug the charger in for the demo")]
    return [Check(INFO, "power", "unknown (no battery info)")]


def probe_screen(root: Path) -> list[Check]:
    out = run(["xrandr", "--current"])
    if out:
        m = re.search(r"current (\d+) x (\d+)", out)
        if m:
            return [Check(INFO, "screen", f"{m.group(1)}x{m.group(2)} (xrandr)")]
    out = run(["system_profiler", "SPDisplaysDataType"], timeout=10)
    if out:
        m = re.search(r"Resolution:\s*(.+)", out)
        if m:
            return [Check(INFO, "screen", m.group(1).strip())]
    return [Check(INFO, "screen", "unknown", "check the projector resolution by hand")]


PROBES: list[Callable[[Path], list[Check]]] = [
    probe_python,
    probe_imports,
    probe_env,
    probe_git,
    probe_port,
    probe_tools,
    probe_power,
    probe_screen,
]


def run_probes(root: Path) -> list[Check]:
    checks: list[Check] = []
    for probe in PROBES:
        try:
            checks.extend(probe(root))
        except Exception as err:  # noqa: BLE001 - a probe must never crash the doctor
            name = probe.__name__.removeprefix("probe_")
            checks.append(Check(WARN, name, f"probe failed: {type(err).__name__}: {err}"))
    return checks


def render(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = []
    for c in checks:
        hint = f"  -> {c.hint}" if c.hint else ""
        lines.append(f"{c.status:<4}  {c.name:<{width}}  {c.detail}{hint}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, help="repo to check (default: the repo of the cwd)")
    args = ap.parse_args(argv)
    root = args.repo.resolve() if args.repo else hackkit_config.repo_root(Path.cwd())
    checks = run_probes(root)
    print(f"hackkit doctor ({root})")
    print(render(checks))
    fails = sum(c.status == FAIL for c in checks)
    warns = sum(c.status == WARN for c in checks)
    print(f"\n{fails} FAIL, {warns} WARN")
    print("Also open http://localhost:8000/#/doctor in the demo browser to check WebGL and fonts.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
