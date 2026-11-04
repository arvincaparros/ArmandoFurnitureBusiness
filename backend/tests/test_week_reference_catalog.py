import json
from decimal import Decimal
from pathlib import Path

from app.data.week_reference_catalog import (
    CATALOG_PRODUCTS,
    CATALOG_REQUIREMENTS,
    CATALOG_RESOURCES,
)


def test_catalog_has_eleven_products():
    assert len(CATALOG_PRODUCTS) == 11
    assert {p.name for p in CATALOG_PRODUCTS} == {
        "Dining table (4 seater)", "Dining table (6 seater)",
        "Dining table (8 seater)", "Ordinary table", "Bed frame",
        "Door (60x210)", "Door (70x210)", "Door (80x210)",
        "Door (90x210)", "High chair", "Ordinary chair",
    }


def test_bedframe_wood_glue_requirement_is_historical_value():
    bed_frame_id = next(
        p.id for p in CATALOG_PRODUCTS if p.name == "Bed frame"
    )
    wood_glue_id = CATALOG_RESOURCES["wood_glue"].id

    requirement = next(
        requirement
        for requirement, resource in CATALOG_REQUIREMENTS
        if requirement.product_id == bed_frame_id
        and resource.id == wood_glue_id
    )

    assert requirement.quantity_required == Decimal("0.3000")


def test_door_products_use_the_verified_two_hour_hand_planer_value():
    hand_planer_id = CATALOG_RESOURCES["hand_planer"].id
    door_ids = {
        p.id for p in CATALOG_PRODUCTS if p.name.startswith("Door (")
    }

    found = 0

    for requirement, resource in CATALOG_REQUIREMENTS:
        if requirement.product_id in door_ids and resource.id == hand_planer_id:
            assert requirement.quantity_required == Decimal("2.0000")
            found += 1

    assert found == 4


def test_week_references_json_has_all_eight_weeks():
    path = (
        Path(__file__).resolve().parents[1]
        / "app" / "data" / "week_references.json"
    )
    data = json.loads(path.read_text())

    assert set(data["weeks"].keys()) == {str(n) for n in range(1, 9)}

    week_one = data["weeks"]["1"]
    assert week_one["resources"]["wood"]["available"] == 1000.0
    assert week_one["resources"]["wood"]["consumed"] == 821.0
    assert week_one["allocation"]["ordinary_chair"] == 10
    assert week_one["total_profit"] == 102236.8148
    assert week_one["is_verified"] is True
