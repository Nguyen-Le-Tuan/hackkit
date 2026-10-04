from hackkit.provenance import DEMO, Sourced, demo_values, source, sourced


def test_label_and_demo_flag():
    assert source("OpenStreetMap", 0.9).label() == "OpenStreetMap (0.90)"
    assert source("Census geocoder").label() == "Census geocoder"
    cost = sourced(8.0, DEMO, note="team-chosen $/sq ft")
    assert cost.source.is_demo and cost.source.label() == "DEMO value"


def test_sourced_round_trips_as_json_the_ui_understands():
    item = sourced(11, "OpenStreetMap", 0.9, note="building:levels")
    data = item.model_dump(mode="json")
    assert data == {
        "value": 11,
        "source": {
            "source": "OpenStreetMap",
            "confidence": 0.9,
            "note": "building:levels",
            "url": None,
        },
    }
    assert Sourced[int].model_validate(data).value == 11


def test_rows_and_demo_list():
    values = {"floors": sourced(11, "OpenStreetMap", 0.9), "cost": sourced(8.0, DEMO)}
    assert demo_values(values) == ["cost"]
    assert values["cost"].as_row("cost")["demo"] is True
