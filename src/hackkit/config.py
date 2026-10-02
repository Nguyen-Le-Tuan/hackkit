"""Settings loaded from environment variables (and a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROVIDERS = ("anthropic", "groq", "ollama", "fake")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    llm_provider: str = "fake"
    llm_model: str = ""
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    demo_mode: bool = False
    timeout_s: float = 60.0
    cache_dir: Path = Path(".cache/hackkit")

    @classmethod
    def from_env(cls) -> Settings:
        provider = os.getenv("LLM_PROVIDER", "fake").strip().lower()
        if provider not in PROVIDERS:
            raise ValueError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
        return cls(
            llm_provider=provider,
            llm_model=os.getenv("LLM_MODEL", "").strip(),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            demo_mode=_env_bool("DEMO_MODE"),
            timeout_s=float(os.getenv("LLM_TIMEOUT_S", "60")),
            cache_dir=Path(os.getenv("HACKKIT_CACHE_DIR", ".cache/hackkit")),
        )
