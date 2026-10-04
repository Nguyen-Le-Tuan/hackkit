import json

from pydantic import Field

from hackkit.ask import Query, apply_query, ask
from hackkit.llm import FakeClient

ROWS = [
    {"name": "Seneca One", "use": "Office", "area": "Downtown", "savings_usd": 235406},
    {"name": "532 Main", "use": "Office", "area": "Downtown", "savings_usd": 99917},
    {"name": "Elm Bakery", "use": "Retail", "area": "Allentown", "savings_usd": 8100},
    {"name": "Allen Lofts", "use": "Office", "area": "Allentown", "savings_usd": 61000},
]


class BuildingQuery(Query):
    use: str | None = Field(default=None, description="Building use, e.g. 'office'.")
    area: str | None = Field(default=None, description="Neighborhood.")
    min_savings_usd: float | None = Field(default=None, description="Savings per year, USD.")


def test_ask_turns_a_question_into_a_filter_and_code_runs_it():
    answer = {"use": "office", "area": None, "min_savings_usd": 50000, "sort_by": "savings_usd",
              "descending": True, "limit": 2}  # fmt: skip
    client = FakeClient([json.dumps(answer)])
    result = ask(client, "top 2 offices saving over $50k", BuildingQuery)
    assert result.ok and "Never answer the question yourself" in client.calls[0].prompt
    rows = apply_query(ROWS, result.data)
    assert [r["name"] for r in rows] == ["Seneca One", "532 Main"]
    assert result.data.explain() == (
        "use = office; savings_usd >= 50,000; sorted by savings_usd desc; top 2"
    )


def test_apply_query_text_contains_and_bounds():
    q = BuildingQuery(area="allen", sort_by="savings_usd", descending=False)
    assert [r["name"] for r in apply_query(ROWS, q)] == ["Elm Bakery", "Allen Lofts"]
    assert apply_query(ROWS, BuildingQuery(use="Factory")) == []
    assert len(apply_query(ROWS, BuildingQuery())) == 4 and BuildingQuery().explain().startswith(
        "no filter"
    )
