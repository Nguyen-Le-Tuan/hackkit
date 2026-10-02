"""Create a new feature in seconds. Run: python -m hackkit.scaffold my_feature "My feature" """

from __future__ import annotations

import argparse
import keyword
import sys
from pathlib import Path

TEMPLATE = '''"""{title}. TODO: one sentence on the user and their pain."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hackkit.feature import Feature, RulesResult, register
from hackkit.schemas import Reviewable, ReviewFlag


class Item(BaseModel):
    # TODO: replace with the real fields. Add `description=` so the LLM knows what you mean.
    name: str = Field(description="TODO")
    evidence: str = Field(default="", description="Exact text from the input that supports this.")


class {class_name}(Reviewable):
    items: list[Item] = Field(default_factory=list)


INSTRUCTIONS = """TODO: Tell the model what to extract and what to ignore.
Never compute totals or scores; only extract what is written."""


def rules(data: {class_name}) -> RulesResult:
    """Deterministic logic: math, thresholds, eligibility. Never ask the LLM to do this."""
    flags: list[ReviewFlag] = []
    if not data.items:
        flags.append(ReviewFlag(field="items", reason="Nothing was extracted."))
    return RulesResult(
        metrics={{"item_count": len(data.items)}},
        flags=flags,
        summary=f"Found {{len(data.items)}} item(s).",
    )


FEATURE = register(
    Feature(
        key="{key}",
        title="{title}",
        description="TODO: what the user gets.",
        schema={class_name},
        instructions=INSTRUCTIONS,
        rules=rules,
        accepts=("text",),
        sample_text="TODO: paste a realistic public or synthetic example here.",
        sample_response='{{"items": [{{"name": "example", "evidence": "example"}}]}}',
    )
)
'''


def create_feature(key: str, title: str, root: Path = Path("src/features")) -> Path:
    if not key.isidentifier() or keyword.iskeyword(key) or not key.islower():
        raise ValueError(f"Feature key must be a lowercase Python identifier, got {key!r}")
    target = root / key
    if target.exists():
        raise FileExistsError(f"{target} already exists")
    target.mkdir(parents=True)
    class_name = "".join(part.capitalize() for part in key.split("_")) + "Result"
    (target / "__init__.py").write_text(
        TEMPLATE.format(key=key, title=title, class_name=class_name), encoding="utf-8"
    )
    return target / "__init__.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a new hackkit feature.")
    parser.add_argument("key", help="lowercase identifier, e.g. intake_triage")
    parser.add_argument("title", nargs="?", default=None)
    args = parser.parse_args(argv)
    path = create_feature(args.key, args.title or args.key.replace("_", " ").capitalize())
    print(f"Created {path}. Restart the app to see it in the sidebar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
