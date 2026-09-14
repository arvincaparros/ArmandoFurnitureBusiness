from datetime import datetime
from decimal import Decimal

from app.database.models import (
    CycleResource,
    Product,
    ProductionCycle,
    ProductResourceRequirement,
    Resource,
)


def test_list_resources_returns_only_active_by_default(client, test_resources, db):
    inactive = test_resources[0]
    inactive.is_active = False
    db.commit()

    response = client.get("/api/resources")

    assert response.status_code == 200

    names = [item["name"] for item in response.json()]

    assert inactive.name not in names
    assert test_resources[1].name in names


def test_list_resources_include_inactive(client, test_resources, db):
    inactive = test_resources[0]
    inactive.is_active = False
    db.commit()

    response = client.get(
        "/api/resources",
        params={"include_inactive": True},
    )

    assert response.status_code == 200

    names = [item["name"] for item in response.json()]

    assert inactive.name in names


def test_list_resources_response_fields(client, test_resources):
    response = client.get("/api/resources")

    assert response.status_code == 200

    item = response.json()[0]

    assert set(item.keys()) == {
        "id",
        "name",
        "resource_type",
        "unit",
        "is_active",
    }


def test_get_resource_by_id(client, test_resources):
    resource = test_resources[0]

    response = client.get(f"/api/resources/{resource.id}")

    assert response.status_code == 200
    assert response.json()["name"] == resource.name


def test_get_resource_not_found(client):
    response = client.get("/api/resources/999999")

    assert response.status_code == 404


def test_create_update_delete_resource(client, cleanup_test_data):
    create_response = client.post(
        "/api/resources",
        json={
            "name": "Test Wood",
            "resource_type": "material",
            "unit": "kg",
        },
    )

    assert create_response.status_code == 201

    resource_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/resources/{resource_id}",
        json={"unit": "tons"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["unit"] == "tons"

    delete_response = client.delete(f"/api/resources/{resource_id}")

    assert delete_response.status_code == 204

    get_response = client.get(f"/api/resources/{resource_id}")

    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


def test_create_resource_unique_name_succeeds(client, cleanup_test_data):
    response = client.post(
        "/api/resources",
        json={
            "name": "Test Wood",
            "resource_type": "material",
            "unit": "kg",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Test Wood"


def test_create_resource_duplicate_name_returns_409(client, test_resources):
    duplicate_name = test_resources[0].name

    response = client.post(
        "/api/resources",
        json={
            "name": duplicate_name,
            "resource_type": "material",
            "unit": "kg",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A resource with this name already exists."
    )


def test_update_resource_duplicate_name_returns_409(client, test_resources):
    first, second = test_resources[0], test_resources[1]

    response = client.patch(
        f"/api/resources/{second.id}",
        json={"name": first.name},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A resource with this name already exists."
    )


def test_cycle_resource_includes_total_value(client, optimization_cycle):
    response = client.get(
        f"/api/production-cycles/{optimization_cycle.id}/resources"
    )

    assert response.status_code == 200

    items = response.json()

    assert len(items) > 0

    for item in items:
        expected_total = Decimal(item["available_quantity"]) * Decimal(
            item["unit_price"]
        )

        assert Decimal(item["total_value"]) == expected_total


def _create_cycle(db):
    cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 9),
        start_date=datetime(2026, 8, 9),
        end_date=datetime(2026, 8, 9),
        status="PLANNED",
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    return cycle


def _delete_cycle(db, cycle):
    db.query(CycleResource).filter(
        CycleResource.production_cycle_id == cycle.id
    ).delete(synchronize_session=False)

    db.delete(cycle)
    db.commit()


def test_create_cycle_resource_labor_allows_zero_unit_price(
    client, db, test_resources
):
    labor = next(r for r in test_resources if r.resource_type == "labor")
    cycle = _create_cycle(db)

    try:
        response = client.post(
            f"/api/production-cycles/{cycle.id}/resources",
            json={
                "resource_id": labor.id,
                "available_quantity": 100,
                "unit_price": 0,
            },
        )

        assert response.status_code == 201
        assert Decimal(response.json()["unit_price"]) == Decimal("0")

    finally:
        _delete_cycle(db, cycle)


def test_create_cycle_resource_non_labor_rejects_zero_unit_price(
    client, db, test_resources
):
    wood = next(r for r in test_resources if r.name == "Test Wood")
    cycle = _create_cycle(db)

    try:
        response = client.post(
            f"/api/production-cycles/{cycle.id}/resources",
            json={
                "resource_id": wood.id,
                "available_quantity": 100,
                "unit_price": 0,
            },
        )

        assert response.status_code == 400

    finally:
        _delete_cycle(db, cycle)


def test_create_cycle_resource_labor_still_requires_positive_quantity(
    client, db, test_resources
):
    labor = next(r for r in test_resources if r.resource_type == "labor")
    cycle = _create_cycle(db)

    try:
        response = client.post(
            f"/api/production-cycles/{cycle.id}/resources",
            json={
                "resource_id": labor.id,
                "available_quantity": 0,
                "unit_price": 0,
            },
        )

        assert response.status_code == 422

    finally:
        _delete_cycle(db, cycle)


def test_update_cycle_resource_labor_allows_zero_unit_price(
    client, db, test_resources
):
    labor = next(r for r in test_resources if r.resource_type == "labor")
    cycle = _create_cycle(db)

    try:
        create_response = client.post(
            f"/api/production-cycles/{cycle.id}/resources",
            json={
                "resource_id": labor.id,
                "available_quantity": 100,
                "unit_price": 50,
            },
        )

        assert create_response.status_code == 201

        update_response = client.patch(
            f"/api/production-cycles/{cycle.id}/resources/{labor.id}",
            json={"unit_price": 0},
        )

        assert update_response.status_code == 200
        assert Decimal(update_response.json()["unit_price"]) == Decimal("0")

    finally:
        _delete_cycle(db, cycle)


def test_update_cycle_resource_non_labor_rejects_zero_unit_price(
    client, db, test_resources
):
    wood = next(r for r in test_resources if r.name == "Test Wood")
    cycle = _create_cycle(db)

    try:
        create_response = client.post(
            f"/api/production-cycles/{cycle.id}/resources",
            json={
                "resource_id": wood.id,
                "available_quantity": 100,
                "unit_price": 84,
            },
        )

        assert create_response.status_code == 201

        update_response = client.patch(
            f"/api/production-cycles/{cycle.id}/resources/{wood.id}",
            json={"unit_price": 0},
        )

        assert update_response.status_code == 400

    finally:
        _delete_cycle(db, cycle)


def test_update_cycle_resource_rejects_explicit_null_unit_price(
    client, db, test_resources
):
    wood = next(r for r in test_resources if r.name == "Test Wood")
    cycle = _create_cycle(db)

    try:
        create_response = client.post(
            f"/api/production-cycles/{cycle.id}/resources",
            json={
                "resource_id": wood.id,
                "available_quantity": 100,
                "unit_price": 84,
            },
        )

        assert create_response.status_code == 201

        update_response = client.patch(
            f"/api/production-cycles/{cycle.id}/resources/{wood.id}",
            json={"unit_price": None},
        )

        assert update_response.status_code == 400

    finally:
        _delete_cycle(db, cycle)


def test_update_cycle_resource_rejects_explicit_null_available_quantity(
    client, db, test_resources
):
    wood = next(r for r in test_resources if r.name == "Test Wood")
    cycle = _create_cycle(db)

    try:
        create_response = client.post(
            f"/api/production-cycles/{cycle.id}/resources",
            json={
                "resource_id": wood.id,
                "available_quantity": 100,
                "unit_price": 84,
            },
        )

        assert create_response.status_code == 201

        update_response = client.patch(
            f"/api/production-cycles/{cycle.id}/resources/{wood.id}",
            json={"available_quantity": None},
        )

        assert update_response.status_code == 400

    finally:
        _delete_cycle(db, cycle)


def test_readd_deleted_resource_reactivates_same_id(client, test_resources):
    deleted = test_resources[0]
    original_id = deleted.id

    delete_response = client.delete(f"/api/resources/{original_id}")
    assert delete_response.status_code == 204

    recreate_response = client.post(
        "/api/resources",
        json={
            "name": deleted.name,
            "resource_type": "labor",
            "unit": "hrs",
        },
    )

    assert recreate_response.status_code == 201

    body = recreate_response.json()

    assert body["id"] == original_id
    assert body["is_active"] is True
    assert body["resource_type"] == "labor"
    assert body["unit"] == "hrs"

    active_names = [
        item["name"]
        for item in client.get("/api/resources").json()
    ]

    assert active_names.count(deleted.name) == 1


def test_readd_deleted_resource_preserves_product_requirements(
    client,
    db,
    test_product_resource_requirements,
    test_resources,
    test_products,
):
    wood = next(r for r in test_resources if r.name == "Test Wood")
    original_id = wood.id

    requirement = (
        db.query(ProductResourceRequirement)
        .filter(ProductResourceRequirement.resource_id == original_id)
        .first()
    )
    assert requirement is not None

    delete_response = client.delete(f"/api/resources/{original_id}")
    assert delete_response.status_code == 204

    recreate_response = client.post(
        "/api/resources",
        json={
            "name": wood.name,
            "resource_type": "material",
            "unit": "kg",
        },
    )

    assert recreate_response.status_code == 201
    assert recreate_response.json()["id"] == original_id

    db.refresh(requirement)

    assert requirement.resource_id == original_id


def test_create_resource_case_and_whitespace_insensitive_duplicate(
    client,
    test_resources,
):
    response = client.post(
        "/api/resources",
        json={
            "name": f"  {test_resources[0].name.upper()}  ",
            "resource_type": "material",
            "unit": "kg",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A resource with this name already exists."
    )


def test_update_resource_case_and_whitespace_insensitive_duplicate(
    client,
    test_resources,
):
    first, second = test_resources[0], test_resources[1]

    response = client.patch(
        f"/api/resources/{second.id}",
        json={"name": f" {first.name.lower()} "},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A resource with this name already exists."
    )


def _create_test_resource(client, name, resource_type="machine", unit="hrs"):
    response = client.post(
        "/api/resources",
        json={
            "name": name,
            "resource_type": resource_type,
            "unit": unit,
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def test_update_resource_capitalization_only_rename_succeeds(client, db):
    resource_id = _create_test_resource(client, "Regression Circular saw")

    try:
        response = client.patch(
            f"/api/resources/{resource_id}",
            json={"name": "Regression Circular Saw"},
        )

        assert response.status_code == 200

        body = response.json()

        assert body["id"] == resource_id
        assert body["name"] == "Regression Circular Saw"

    finally:
        db.query(Resource).filter(Resource.id == resource_id).delete()
        db.commit()


def test_update_resource_whitespace_cleanup_rename_succeeds(client, db):
    resource_id = _create_test_resource(client, "Regression Table Saw")

    try:
        response = client.patch(
            f"/api/resources/{resource_id}",
            json={"name": "  Regression Table Saw  "},
        )

        assert response.status_code == 200

        body = response.json()

        assert body["id"] == resource_id
        assert body["name"] == "Regression Table Saw"

    finally:
        db.query(Resource).filter(Resource.id == resource_id).delete()
        db.commit()


def test_update_resource_normalized_conflict_with_active_other_row_blocks_rename(
    client, db,
):
    saw_id = _create_test_resource(client, "Regression Circular Saw")
    other_id = _create_test_resource(client, "Regression Band Saw")

    try:
        response = client.patch(
            f"/api/resources/{other_id}",
            json={"name": "regression circular saw"},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == (
            "A resource with this name already exists."
        )

        # The rename must not have gone through - resource 456 stays
        # itself, it is not merged into resource 123.
        unchanged = client.get(f"/api/resources/{other_id}").json()
        assert unchanged["name"] == "Regression Band Saw"

    finally:
        db.query(Resource).filter(
            Resource.id.in_([saw_id, other_id])
        ).delete(synchronize_session=False)
        db.commit()


def test_update_resource_normalized_conflict_with_inactive_other_row_blocks_rename(
    client, db,
):
    # id=123-equivalent: soft-deleted, still holds the normalized name.
    deleted_id = _create_test_resource(client, "Regression Circular Saw")

    delete_response = client.delete(f"/api/resources/{deleted_id}")
    assert delete_response.status_code == 204

    # id=456-equivalent: a different, active resource being edited.
    other_id = _create_test_resource(client, "Regression Band Saw")

    try:
        response = client.patch(
            f"/api/resources/{other_id}",
            json={"name": "Regression Circular Saw"},
        )

        # Must BLOCK, not silently reactivate/merge into the inactive
        # row - that reuse-on-name-match behavior belongs only to
        # create_resource's delete+re-add path, never to update.
        assert response.status_code == 409
        assert response.json()["detail"] == (
            "A resource with this name already exists."
        )

        other_after = client.get(f"/api/resources/{other_id}").json()
        assert other_after["name"] == "Regression Band Saw"
        assert other_after["is_active"] is True

        deleted_after = client.get(f"/api/resources/{deleted_id}").json()
        assert deleted_after["name"] == "Regression Circular Saw"
        assert deleted_after["is_active"] is False

    finally:
        db.query(Resource).filter(
            Resource.id.in_([deleted_id, other_id])
        ).delete(synchronize_session=False)
        db.commit()


def test_update_resource_capitalization_rename_preserves_product_requirements(
    client, db,
):
    resource_id = _create_test_resource(client, "Regression Circular saw")

    product = Product(
        name="Regression Test Product",
        selling_price=Decimal("100.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    requirement = ProductResourceRequirement(
        product_id=product.id,
        resource_id=resource_id,
        quantity_required=Decimal("2.0000"),
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)

    try:
        response = client.patch(
            f"/api/resources/{resource_id}",
            json={"name": "Regression Circular Saw"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == resource_id

        db.refresh(requirement)

        assert requirement.resource_id == resource_id
        assert requirement.quantity_required == Decimal("2.0000")

        requirements_response = client.get(
            f"/api/products/{product.id}/resources"
        )

        assert requirements_response.status_code == 200

        items = requirements_response.json()
        assert len(items) == 1
        assert items[0]["resource_id"] == resource_id

    finally:
        db.query(ProductResourceRequirement).filter(
            ProductResourceRequirement.product_id == product.id
        ).delete(synchronize_session=False)
        db.query(Product).filter(Product.id == product.id).delete()
        db.query(Resource).filter(Resource.id == resource_id).delete()
        db.commit()


def test_update_resource_combined_rename_and_field_edit_succeeds(client, db):
    resource_id = _create_test_resource(
        client, "Regression Combined Saw", resource_type="material", unit="kg",
    )

    try:
        response = client.patch(
            f"/api/resources/{resource_id}",
            json={
                "name": "  regression combined saw  ",
                "resource_type": "machine",
                "unit": "hrs",
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["id"] == resource_id
        assert body["name"] == "regression combined saw"
        assert body["resource_type"] == "machine"
        assert body["unit"] == "hrs"

    finally:
        db.query(Resource).filter(Resource.id == resource_id).delete()
        db.commit()


def _resource_row_count(db):
    return db.query(Resource).count()


def test_create_endpoint_rejects_every_case_and_whitespace_variant(client, db):
    """
    Full end-to-end regression for the actual POST /api/resources route
    (not just the service function) - covers create-active-collision,
    create-inactive-restore, and confirms the resources table's row
    count never grows on a rejected duplicate, for every case/whitespace
    variant of one name.
    """
    original_count = _resource_row_count(db)

    resource_id = _create_test_resource(
        client, "Regression Endpoint Circular Saw",
        resource_type="machine", unit="hrs",
    )

    assert _resource_row_count(db) == original_count + 1

    try:
        variants = [
            "regression endpoint circular saw",
            "REGRESSION ENDPOINT CIRCULAR SAW",
            "  Regression Endpoint Circular Saw  ",
            "Regression Endpoint Circular Saw",  # exact duplicate too
        ]

        for variant in variants:
            count_before = _resource_row_count(db)

            response = client.post(
                "/api/resources",
                json={
                    "name": variant,
                    "resource_type": "material",
                    "unit": "kg",
                },
            )

            assert response.status_code == 409, (
                f"expected 409 for variant {variant!r}, got "
                f"{response.status_code}: {response.text}"
            )
            assert response.json()["detail"] == (
                "A resource with this name already exists."
            )
            assert _resource_row_count(db) == count_before, (
                f"row count changed after rejected create of {variant!r}"
            )

        # Soft-delete, then re-add a case-variant name - must reactivate
        # the SAME row, not insert a new one.
        delete_response = client.delete(f"/api/resources/{resource_id}")
        assert delete_response.status_code == 204

        count_before_readd = _resource_row_count(db)

        readd_response = client.post(
            "/api/resources",
            json={
                "name": "regression endpoint circular saw",
                "resource_type": "machine",
                "unit": "hrs",
            },
        )

        assert readd_response.status_code == 201
        body = readd_response.json()
        assert body["id"] == resource_id
        assert body["is_active"] is True
        assert _resource_row_count(db) == count_before_readd

        # No lingering normalized-name duplicate group for this name.
        matching = [
            r for r in db.query(Resource).all()
            if r.name.strip().lower() == "regression endpoint circular saw"
        ]
        assert len(matching) == 1
        assert matching[0].id == resource_id

    finally:
        db.query(Resource).filter(Resource.id == resource_id).delete()
        db.commit()


# --- Capacity-integrity guard: reducing CycleResource.available_quantity ---
#
# optimization_cycle's baseline optimum (no minimum_demand set) is
# Chair=12, Bed Frame=12 - Wood consumption 12*12 + 12*55 = 804,
# Labor consumption 12*8 + 12*40 = 576 (exactly saturating Labor's own
# 576 available - see test_optimization.py::
# test_optimization_returns_optimal_solution).


def test_update_cycle_resource_rejects_reduction_below_applied_consumption(
    client, db, optimization_cycle, test_resources,
):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    resources_by_name = {r.name: r for r in test_resources}
    wood = resources_by_name["Test Wood"]

    response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{wood.id}",
        json={"available_quantity": 500},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Wood" in detail
    assert "804" in detail

    cycle_resource = db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id,
        CycleResource.resource_id == wood.id,
    ).first()
    assert cycle_resource.available_quantity == Decimal("1250.0000")


def test_update_cycle_resource_allows_capacity_increase(
    client, db, optimization_cycle, test_resources,
):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    resources_by_name = {r.name: r for r in test_resources}
    wood = resources_by_name["Test Wood"]

    response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{wood.id}",
        json={"available_quantity": 2000},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["available_quantity"]) == Decimal("2000")


def test_update_cycle_resource_unit_price_only_edit_not_blocked_by_capacity(
    client, db, optimization_cycle, test_resources,
):
    """
    A unit-price-only PATCH (no available_quantity key at all) must
    never be blocked by the capacity-reduction guard, even though the
    resource is fully consumed by an already-applied allocation.
    """

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    resources_by_name = {r.name: r for r in test_resources}
    wood = resources_by_name["Test Wood"]

    response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{wood.id}",
        json={"unit_price": 99},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["unit_price"]) == Decimal("99")


def test_update_cycle_resource_labor_capacity_reduction_still_validated(
    client, db, optimization_cycle, test_resources,
):
    """
    Labor is exempt from the positive-unit-price rule (it may be 0 -
    product labor cost is tracked separately via Product.labor_cost),
    but it is NOT exempt from the capacity-integrity guard: it still
    physically constrains production and the already-applied
    allocation saturates it exactly (576/576 hours).
    """

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    resources_by_name = {r.name: r for r in test_resources}
    labor = resources_by_name["Test Labor"]

    response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{labor.id}",
        json={"available_quantity": 100, "unit_price": 0},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Labor" in detail
    assert "576" in detail


def test_update_cycle_resource_labor_zero_unit_price_still_valid(
    client, db, optimization_cycle, test_resources,
):
    """
    Regression: Labor's zero-unit-price exception (Revision from the
    earlier student-feedback fix) must remain valid when nothing about
    capacity is being reduced.
    """

    resources_by_name = {r.name: r for r in test_resources}
    labor = resources_by_name["Test Labor"]

    response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{labor.id}",
        json={"unit_price": 0},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["unit_price"]) == Decimal("0")


def test_update_cycle_resource_inactive_resource_capacity_reduction_not_blocked(
    client, db, optimization_cycle, test_resources,
):
    """
    An inactive resource is already treated as zero capacity
    everywhere it matters (the optimizer's own resource constraint,
    and it's filtered out of the Resource Utilization Report entirely)
    - so reducing its stored available_quantity, even below whatever a
    stale applied allocation implies it consumed, has no real safety
    impact and must not be blocked.
    """

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    resources_by_name = {r.name: r for r in test_resources}
    wood = resources_by_name["Test Wood"]
    wood.is_active = False
    db.commit()

    try:
        response = client.patch(
            f"/api/production-cycles/{optimization_cycle.id}/resources/{wood.id}",
            json={"available_quantity": 1},
        )

        assert response.status_code == 200
    finally:
        wood.is_active = True
        db.commit()
