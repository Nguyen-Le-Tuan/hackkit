"""Ask your data in plain English: the LLM turns a question into a FILTER, code runs it.

    class BuildingQuery(Query):
        use: str | None = Field(None, description="Building use, e.g. 'office'.")
        min_savings_usd: float | None = Field(None, description="Lower bound on savings.")
        neighborhood: str | None = None

    q = ask(client, "offices in Allentown saving over $50k", BuildingQuery)
    rows = apply_query(buildings, q.data)        # deterministic, testable, explainable
    q.data.explain()  # "use = office; neighborhood = Allentown; savings_usd >= 50,000"

The model never sees or returns the rows, so it cannot invent results: it only fills the
filter. Field-name conventions understood by apply_query:
  <col>            equals (case-insensitive for text; "contains" when the value has spaces)
  min_<col>        >=          max_<col>   <=
  sort_by          column name;  descending (bool);  limit (int)
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from .cache import DiskCache
from .extract import Extraction, extract
from .llm.base import LLMClient

INSTRUCTIONS = """Turn the user's question into filter values for a table.
Fill only the fields the question clearly asks for; leave every other field null.
Use the units in the field descriptions (e.g. write 50000 for "$50k").
Never answer the question yourself and never invent values that are not in the question."""


class Query(BaseModel):
    """Base class for a filter the model fills. Add your columns as optional fields."""

    sort_by: str | None = Field(default=None, description="Column to sort by, if asked.")
    descending: bool = Field(default=True, description="Sort largest first unless asked.")
    limit: int | None = Field(default=None, ge=1, le=1000, description="How many rows, if asked.")

    def filters(self) -> dict[str, Any]:
        skip = {"sort_by", "descending", "limit"}
        return {k: v for k, v in self.model_dump().items() if k not in skip and v is not None}

    def explain(self) -> str:
        """Readable filter, to show next to the results ("what the AI understood")."""
        parts = []
        for key, value in self.filters().items():
            if isinstance(value, float) and value.is_integer():
                shown = f"{value:,.0f}"
            elif isinstance(value, int | float):
                shown = f"{value:,}"
            else:
                shown = str(value)
            if key.startswith("min_"):
                parts.append(f"{key[4:]} >= {shown}")
            elif key.startswith("max_"):
                parts.append(f"{key[4:]} <= {shown}")
            else:
                parts.append(f"{key} = {shown}")
        if self.sort_by:
            parts.append(f"sorted by {self.sort_by} {'desc' if self.descending else 'asc'}")
        if self.limit:
            parts.append(f"top {self.limit}")
        return "; ".join(parts) or "no filter (all rows)"


Q = TypeVar("Q", bound=Query)


def ask(
    client: LLMClient,
    question: str,
    query_schema: type[Q],
    *,
    context: str = "",
    cache: DiskCache | None = None,
    demo_mode: bool = False,
) -> Extraction[Q]:
    """Question -> validated filter object (same retry/cache/demo rules as extract)."""
    instructions = INSTRUCTIONS + (f"\n\nAbout the data: {context.strip()}" if context else "")
    return extract(
        client,
        query_schema,
        instructions=instructions,
        text=question,
        cache=cache,
        demo_mode=demo_mode,
        max_tokens=512,
    )


def _match_text(cell: Any, wanted: str) -> bool:
    if cell is None:
        return False
    cell_text, wanted_text = str(cell).casefold(), wanted.casefold().strip()
    return cell_text == wanted_text or (len(wanted_text) > 2 and wanted_text in cell_text)


def apply_query(rows: Iterable[Mapping[str, Any]], query: Query) -> list[Mapping[str, Any]]:
    """Run the filter deterministically over plain dict rows."""
    out = []
    for row in rows:
        keep = True
        for key, wanted in query.filters().items():
            if key.startswith("min_"):
                cell = row.get(key[4:])
                keep = isinstance(cell, int | float) and cell >= wanted
            elif key.startswith("max_"):
                cell = row.get(key[4:])
                keep = isinstance(cell, int | float) and cell <= wanted
            elif isinstance(wanted, str):
                keep = _match_text(row.get(key), wanted)
            else:
                keep = row.get(key) == wanted
            if not keep:
                break
        if keep:
            out.append(row)
    if query.sort_by:
        present = [r for r in out if isinstance(r.get(query.sort_by), int | float | str)]
        missing = [r for r in out if r not in present]
        present.sort(key=lambda r: r[query.sort_by], reverse=query.descending)
        out = present + missing
    return out[: query.limit] if query.limit else out
