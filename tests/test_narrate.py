from hackkit.llm import FakeClient, LLMError
from hackkit.narrate import check_numbers, fallback_text, narrate, numbers_in

FACTS = {"computed_total": 24.56, "stated_total": 24.6, "difference": 0.04, "item_count": 3}


def test_numbers_in_finds_money_percent_and_suffixes():
    assert numbers_in("Paid $1,234.50 (35%) for 3 items, about $235k.") == [
        "$1,234.50", "35%", "3", "$235k",
    ]  # fmt: skip


def test_rounded_and_formatted_facts_are_accepted():
    assert check_numbers("Total $24.56, printed $24.60, off by $0.04.", FACTS) == []
    assert check_numbers("Saves $235k a year.", {"savings": 235406}) == []
    assert check_numbers("A 35% margin.", {"margin": 0.351}) == []
    assert check_numbers("About 24.6 dollars.", FACTS) == []


def test_invented_numbers_are_rejected_but_small_counts_pass():
    assert check_numbers("The customer could save $12.30 per month.", FACTS) == ["$12.30"]
    assert check_numbers("Based on 2026 data.", FACTS) == ["2026"]
    assert check_numbers("Three items, 3 lines, 1 receipt.", FACTS) == []


def test_narrate_retries_then_accepts_a_clean_answer(cache):
    client = FakeClient(
        ["You were overcharged $5.", "The receipt says $24.60 but adds up to $24.56."]
    )
    result = narrate(client, FACTS, instructions="Explain.", cache=cache)
    assert result.ok and result.attempts == 2 and "$24.56" in result.text
    assert "not in FACTS: $5" in client.calls[1].prompt and client.calls[0].json_mode is False
    again = narrate(FakeClient([]), FACTS, instructions="Explain.", cache=cache)
    assert again.from_cache and again.text == result.text


def test_narrate_falls_back_instead_of_showing_a_wrong_number():
    client = FakeClient(["Save $99.", "Still $99."])
    result = narrate(client, FACTS, instructions="Explain.")
    assert not result.ok and result.fallback and result.problems == ["$99"]
    assert result.text == fallback_text(FACTS) and "24.56" in result.text


def test_narrate_survives_provider_errors_and_demo_mode():
    def boom(_request):
        raise LLMError("offline")

    assert narrate(FakeClient(boom), FACTS, instructions="x").fallback
    demo = narrate(FakeClient([]), FACTS, instructions="x", demo_mode=True)
    assert demo.ok and demo.fallback
