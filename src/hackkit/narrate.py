"""AI that explains, with every number checked: the LLM writes the words, code owns the numbers.

    result = narrate(client, {"computed_total": 24.56, "stated_total": 24.60},
                     instructions="Explain to the shop owner whether the receipt adds up.")
    result.text      # plain-English paragraph
    result.ok        # True when every number in the text matches a computed fact
    result.problems  # numbers the model invented, if any (then we retried / fell back)

Why: judges want to SEE the AI, and they punish a wrong number. The model may only repeat the
numbers it is given (rounded or formatted is fine: 24.56 -> "$24.56", 0.351 -> "35%",
235406 -> "$235k"). Any other number triggers one retry with feedback, then a deterministic
fallback text, so the demo never shows an invented figure.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .cache import DiskCache
from .llm.base import LLMClient, LLMError, LLMRequest

SYSTEM = """You write short, plain-English explanations of results that code has computed.
Rules:
- Use ONLY the numbers in FACTS. You may round or format them ($, %, k, M) but never compute,
  estimate or invent another number (no sums, differences, ratios, years or counts of your own).
- If a number you would like to mention is not in FACTS, describe it in words instead.
- No markdown, no lists, no headings. At most {max_words} words. Audience: {audience}."""

NUMBER = re.compile(r"(?<![\w.])-?\$?\d[\d,]*(?:\.\d+)?(?:\s?%|\s?[kKmMbB](?![a-zA-Z]))?")
SMALL_INTS = set(range(0, 11))  # "3 items", "1 of 2": counts this small rarely mislead


@dataclass
class Narration:
    text: str
    ok: bool
    attempts: int = 0
    from_cache: bool = False
    fallback: bool = False
    problems: list[str] = field(default_factory=list)


def _parse(token: str) -> tuple[float, int, str]:
    """'$1,234.5k' -> (1234500.0, decimals=1, unit='k'). unit in {'', '%', 'k', 'm', 'b'}."""
    raw = token.replace("$", "").replace(",", "").replace(" ", "")
    unit = ""
    if raw[-1:] in "%kKmMbB":
        unit = raw[-1].lower()
        raw = raw[:-1]
    decimals = len(raw.split(".", 1)[1]) if "." in raw else 0
    value = float(raw)
    scale = {"k": 1e3, "m": 1e6, "b": 1e9}.get(unit, 1.0)
    return value * scale, decimals, unit


def numbers_in(text: str) -> list[str]:
    return [m.group(0).strip() for m in NUMBER.finditer(text)]


def _matches(token: str, fact: float, rel_tol: float) -> bool:
    value, decimals, unit = _parse(token)
    candidates = [fact]
    if unit == "%":
        candidates = [fact * 100, fact]  # 0.35 -> "35%", or a fact already in percent
    for target in candidates:
        if unit in {"k", "m", "b"}:
            step = {"k": 1e3, "m": 1e6, "b": 1e9}[unit] * 10**-decimals
        else:
            step = 10**-decimals
        if abs(value - target) <= max(step / 2 + 1e-9, abs(target) * rel_tol):
            return True
    return False


def check_numbers(
    text: str,
    facts: Mapping[str, Any],
    *,
    rel_tol: float = 0.005,
    allow: tuple[float, ...] = (),
) -> list[str]:
    """Numbers in `text` that match no fact (after rounding/formatting). Empty = all good."""
    values = [float(v) for v in _flatten(facts) if isinstance(v, int | float) and math.isfinite(v)]
    values += list(allow)
    problems = []
    for token in numbers_in(text):
        number, decimals, unit = _parse(token)
        if "$" not in token and not unit and decimals == 0 and number in SMALL_INTS:
            continue  # "3 items" is fine; "$5" is money and must match a fact
        if not any(_matches(token, fact, rel_tol) for fact in values):
            problems.append(token)
    return problems


def _flatten(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        return [x for v in value.values() for x in _flatten(v)]
    if isinstance(value, list | tuple):
        return [x for v in value for x in _flatten(v)]
    if isinstance(value, bool):
        return []
    return [value]


def fallback_text(facts: Mapping[str, Any]) -> str:
    """Deterministic text used when the model keeps inventing numbers."""
    parts = []
    for key, value in facts.items():
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            continue
        shown = f"{value:,.2f}" if isinstance(value, float) else str(value)
        parts.append(f"{key.replace('_', ' ')}: {shown}")
    return "Key results. " + "; ".join(parts) + "." if parts else "No results to explain."


def narrate(
    client: LLMClient,
    facts: Mapping[str, Any],
    *,
    instructions: str,
    audience: str = "a busy, non-technical decision maker",
    max_words: int = 90,
    cache: DiskCache | None = None,
    demo_mode: bool = False,
    max_attempts: int = 2,
    allow: tuple[float, ...] = (),
    fallback: Callable[[Mapping[str, Any]], str] = fallback_text,
) -> Narration:
    facts_json = json.dumps(facts, sort_keys=True, ensure_ascii=False, default=str)
    system = SYSTEM.format(max_words=max_words, audience=audience)
    prompt = f"{instructions.strip()}\n\nFACTS (computed by code):\n{facts_json}"
    key = DiskCache.make_key(
        "narrate", getattr(client, "name", "?"), getattr(client, "model", "?"), system, prompt
    )
    if cache is not None and (cached := cache.get(key)) is not None:
        return Narration(cached, ok=True, from_cache=True)
    if demo_mode:
        return Narration(fallback(facts), ok=True, fallback=True)

    current, problems, attempts = prompt, [], 0
    for attempts in range(1, max_attempts + 1):  # noqa: B007 - reported below
        try:
            text = client.complete(
                LLMRequest(system=system, prompt=current, max_tokens=400, json_mode=False)
            ).text.strip()
        except LLMError as exc:
            problems = [f"model error: {exc}"]
            continue
        text = re.sub(r"\s+", " ", text.replace("**", "")).strip()
        problems = check_numbers(text, facts, allow=allow)
        if not problems and text:
            if cache is not None:
                cache.set(key, text)
            return Narration(text, ok=True, attempts=attempts)
        current = (
            f"{prompt}\n\nYour previous answer used numbers that are not in FACTS: "
            f"{', '.join(problems) or '(empty answer)'}. Rewrite it using only FACTS numbers."
        )
    return Narration(fallback(facts), ok=False, attempts=attempts, fallback=True, problems=problems)
