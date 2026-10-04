"""Create a new feature in seconds: `make feature NAME=my_feature TITLE="My feature" [PAGE=1]`.

Writes src/features/<key>/__init__.py (schema + rules + optional "Explain" narrative),
tests/test_<key>.py (rules tested without a model), evals/cases/<key>.jsonl (accuracy cases)
and, with --page, a custom web page registered in web/js/pages/index.js.
"""

from __future__ import annotations

import argparse
import json
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
        # Makes the AI visible: an "Explain" button where the model explains the result in plain
        # English and code rejects any number not in the metrics. Delete both lines to hide it.
        narrative="Explain the result to the user in two plain sentences.",
        sample_narrative="We found 1 item in this input.",
    )
)
'''

TEST_TEMPLATE = '''"""Rules for {key}: tested without a model (the LLM never decides a number)."""

from features.{key} import FEATURE, {class_name}, rules


def test_rules_count_the_items():
    data = {class_name}.model_validate_json(FEATURE.sample_response)
    result = rules(data)
    assert result.metrics["item_count"] == len(data.items)


def test_rules_flag_an_empty_input():
    assert rules({class_name}()).flags  # TODO: replace with your real edge cases
'''

PAGE_TEMPLATE = """// Custom page for {title}. Registered in web/js/pages/index.js (route #/{key}).
// Build from the kit (#/kit): cards, metrics, tables, map, chart. Data comes from api.js.

import * as api from "../api.js";
import * as fmt from "../fmt.js";
import {{ h, card, metricTile, metrics, emptyState, button }} from "../ui.js";

export async function render() {{
  const feature = await api.feature("{key}");
  const out = h("div", {{}}, emptyState("Press Run to see the result."));
  const run = async () => {{
    const result = await api.run("{key}", {{ text: feature.sample_text }});
    out.replaceChildren(
      metrics(Object.entries(result.metrics).map(([k, v]) => metricTile(fmt.humanize(k), fmt.metric(k, v)))),
    );
  }};
  return h(
    "div",
    {{ class: "page fade-in" }},
    h("header", {{ class: "page-head" }}, h("div", {{}}, h("div", {{ class: "eyebrow" }}, "Demo"), h("h1", {{}}, "{title}"))),
    card({{ title: "Result", actions: button("Run", {{ kind: "primary", iconName: "play", onClick: run }}) }}, out),
  );
}}
"""


def _class_name(key: str) -> str:
    return "".join(part.capitalize() for part in key.split("_")) + "Result"


def create_extras(
    key: str, title: str, repo: Path = Path("."), *, page: bool = False
) -> list[Path]:
    """Test file, eval case and (optionally) a web page for a new feature."""
    created = []
    test = repo / "tests" / f"test_{key}.py"
    if not test.exists():
        test.parent.mkdir(parents=True, exist_ok=True)
        test.write_text(
            TEST_TEMPLATE.format(key=key, class_name=_class_name(key)), encoding="utf-8"
        )
        created.append(test)
    cases = repo / "evals" / "cases" / f"{key}.jsonl"
    if not cases.exists():
        cases.parent.mkdir(parents=True, exist_ok=True)
        case = {
            "feature": key,
            "text": "TODO: a realistic input",
            "expected": {"items": [{"name": "example", "evidence": "example"}]},
        }
        cases.write_text(json.dumps(case) + "\n", encoding="utf-8")
        created.append(cases)
    if page:
        page_file = repo / "web" / "js" / "pages" / f"{key}.js"
        registry = repo / "web" / "js" / "pages" / "index.js"
        if not page_file.exists():
            page_file.parent.mkdir(parents=True, exist_ok=True)
            page_file.write_text(PAGE_TEMPLATE.format(key=key, title=title), encoding="utf-8")
            created.append(page_file)
        if registry.exists():
            text = registry.read_text(encoding="utf-8")
            line = f'  {{ path: "/{key}", title: "{title}", icon: "spark", nav: true, render: {key}.render }},'
            if f"./{key}.js" not in text and "export const pages = [" in text:
                text = f'import * as {key} from "./{key}.js";\n' + text
                if "export const pages = [];" in text:
                    text = text.replace(
                        "export const pages = [];", f"export const pages = [\n{line}\n];"
                    )
                else:
                    text = text.replace(
                        "export const pages = [", f"export const pages = [\n{line}", 1
                    )
                registry.write_text(text, encoding="utf-8")
                created.append(registry)
    return created


def create_feature(key: str, title: str, root: Path = Path("src/features")) -> Path:
    if not key.isidentifier() or keyword.iskeyword(key) or not key.islower():
        raise ValueError(f"Feature key must be a lowercase Python identifier, got {key!r}")
    target = root / key
    if target.exists():
        raise FileExistsError(f"{target} already exists")
    target.mkdir(parents=True)
    class_name = _class_name(key)
    (target / "__init__.py").write_text(
        TEMPLATE.format(key=key, title=title, class_name=class_name), encoding="utf-8"
    )
    return target / "__init__.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a new hackkit feature.")
    parser.add_argument("key", help="lowercase identifier, e.g. intake_triage")
    parser.add_argument("title", nargs="?", default=None)
    parser.add_argument("--page", action="store_true", help="also create a custom web page")
    args = parser.parse_args(argv)
    title = args.title or args.key.replace("_", " ").capitalize()
    path = create_feature(args.key, title)
    extras = create_extras(args.key, title, page=args.page)
    for created in [path, *extras]:
        print(f"created {created}")
    print("Next: edit the schema, INSTRUCTIONS and rules(); `make test`; refresh the browser:")
    print(f"the feature is at #/feature/{args.key}" + (f" and #/{args.key}" if args.page else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
