"""Start the app (API + web UI) on a free port for screenshots, videos and smoke tests.

    with app_server() as base:          # starts uvicorn, waits for /api/health
        page.goto(f"{base}/#/kit")
    with app_server(base="http://localhost:8000"):   # reuse a server that is already running
        ...

The provider comes from the environment (.env), so `make shots` shows real model results when
.env says so; set LLM_PROVIDER=fake to capture without a key.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(url: str, timeout: float = 25.0) -> None:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - any failure means "not up yet"
            last = exc
        time.sleep(0.3)
    raise RuntimeError(f"server did not answer {url} within {timeout:.0f}s: {last}")


@contextlib.contextmanager
def app_server(base: str | None = None, env: dict[str, str] | None = None) -> Iterator[str]:
    """Yield the base URL of a running app; start (and later stop) one if `base` is None."""
    if base:
        wait_for(f"{base.rstrip('/')}/api/health", timeout=5)
        yield base.rstrip("/")
        return
    port = free_port()
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "--factory",
        "hackkit.server:create_app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    process = subprocess.Popen(command, cwd=ROOT, env={**os.environ, **(env or {})})
    url = f"http://127.0.0.1:{port}"
    try:
        wait_for(f"{url}/api/health")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
