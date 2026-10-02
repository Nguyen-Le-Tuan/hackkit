"""Tiny disk cache. Every successful LLM or API response is stored, so a demo can replay it."""

from __future__ import annotations

import hashlib
from pathlib import Path


class DiskCache:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def make_key(*parts: str) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update(part.encode("utf-8"))
            digest.update(b"\x00")
        return digest.hexdigest()

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.txt"

    def get(self, key: str) -> str | None:
        path = self._path(key)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def set(self, key: str, value: str) -> None:
        self._path(key).write_text(value, encoding="utf-8")

    def clear(self) -> int:
        removed = 0
        for path in self.directory.glob("*.txt"):
            path.unlink()
            removed += 1
        return removed
