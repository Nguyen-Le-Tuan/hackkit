"""Example feature: receipt checker. Shows the core pattern on a neutral domain.

The LLM reads the receipt and lists what is written. Python does the arithmetic and
flags a mismatch, because a demo that says "the math is checked by code" is trustworthy.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from hackkit.feature import Feature, RulesResult, register
from hackkit.schemas import Reviewable, ReviewFlag


class LineItem(BaseModel):
    description: str = Field(description="Item name as printed.")
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(ge=0, description="Price for one unit, as printed.")
    evidence: str = Field(default="", description="Exact receipt line this item came from.")


class Receipt(Reviewable):
    merchant: str | None = None
    date: str | None = Field(default=None, description="Date as printed, ISO if obvious.")
    currency: str = "USD"
    items: list[LineItem] = Field(default_factory=list)
    tax: float = Field(default=0, ge=0)
    stated_total: float | None = Field(default=None, description="Total printed on the receipt.")


INSTRUCTIONS = """Extract the merchant, date, line items, tax and printed total from this receipt.
Copy numbers exactly as printed. Do not add up anything yourself."""


def rules(receipt: Receipt) -> RulesResult:
    computed = round(sum(i.quantity * i.unit_price for i in receipt.items) + receipt.tax, 2)
    flags: list[ReviewFlag] = []
    if receipt.stated_total is None:
        flags.append(ReviewFlag(field="stated_total", reason="No printed total was found."))
    elif abs(computed - receipt.stated_total) > 0.01:
        flags.append(
            ReviewFlag(
                field="stated_total",
                reason=f"Items plus tax add up to {computed:.2f}, "
                f"but the receipt says {receipt.stated_total:.2f}.",
            )
        )
    summary = f"{len(receipt.items)} item(s) from {receipt.merchant or 'an unknown merchant'}."
    metrics = {"computed_total": computed, "item_count": len(receipt.items)}
    if receipt.stated_total is not None:
        metrics["stated_total"] = receipt.stated_total
        metrics["difference"] = round(receipt.stated_total - computed, 2)
    return RulesResult(
        metrics=metrics,
        flags=flags,
        summary=summary,
    )


# The printed total is 0.04 off on purpose, so the demo shows the code catching it.
SAMPLE_TEXT = """CORNER MARKET  -  2026-09-12
2 x Oat milk        3.49
1 x Bagels (6)      4.25
1 x Coffee beans   11.99
Tax                 1.34
TOTAL              24.60"""

SAMPLE_RESPONSE = json.dumps(
    {
        "merchant": "Corner Market",
        "date": "2026-09-12",
        "currency": "USD",
        "items": [
            {
                "description": "Oat milk",
                "quantity": 2,
                "unit_price": 3.49,
                "evidence": "2 x Oat milk 3.49",
            },
            {
                "description": "Bagels (6)",
                "quantity": 1,
                "unit_price": 4.25,
                "evidence": "1 x Bagels (6) 4.25",
            },
            {
                "description": "Coffee beans",
                "quantity": 1,
                "unit_price": 11.99,
                "evidence": "1 x Coffee beans 11.99",
            },
        ],
        "tax": 1.34,
        "stated_total": 24.60,
        "confidence": 0.9,
        "uncertain_fields": [],
    }
)

NARRATIVE = """Explain to the shop owner, in two sentences, whether this receipt adds up and
what they should do about it. Mention the printed total and the computed total."""

# What the fake provider says when you click "Explain" (every number is in the metrics).
SAMPLE_NARRATIVE = (
    "The receipt says $24.60, but the items plus tax add up to $24.56, so the customer was "
    "overcharged by $0.04. Check the register and refund the difference."
)

FEATURE = register(
    Feature(
        key="receipt",
        title="Receipt checker",
        description="Reads a receipt and checks that the items add up to the printed total.",
        schema=Receipt,
        instructions=INSTRUCTIONS,
        rules=rules,
        accepts=("text", "image", "pdf"),
        sample_text=SAMPLE_TEXT,
        sample_response=SAMPLE_RESPONSE,
        tags=("example",),
        narrative=NARRATIVE,
        sample_narrative=SAMPLE_NARRATIVE,
    )
)
