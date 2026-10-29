from datetime import datetime
from decimal import Decimal

from app.database.models import (
    CycleResource,
    Product,
    ProductionAllocation,
    ProductionCycle,
    ProductResourceRequirement,
    Resource,
    ResourceUtilizationHistoryItem,
    ResourceUtilizationRun,
)
from app.services.resource import DUPLICATE_INACTIVE_NAME_ERROR


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


def test_readd_deleted_resource_is_rejected_without_reactivating(
    client, db, test_resources,
):
    deleted = test_resources[0]
    original_id = deleted.id
    original_type = deleted.resource_type
    original_unit = deleted.unit

    delete_response = client.delete(f"/api/resources/{original_id}")
    assert delete_response.status_code == 204

    recreate_response = client.post(
        "/api/resources",
        json={
            "name": f"  {deleted.name.upper()}  ",
            "resource_type": "labor",
            "unit": "hrs",
        },
    )

    assert recreate_response.status_code == 409
    assert (
        recreate_response.json()["detail"]
        == DUPLICATE_INACTIVE_NAME_ERROR
    )

    # The soft-deleted row is left exactly as it was - no silent
    # reactivation with the POSTed fields, and no second row under
    # the same normalized name.
    db.expire_all()

    matching = [
        resource
        for resource in db.query(Resource).all()
        if resource.name.strip().lower()
        == deleted.name.strip().lower()
    ]

    assert len(matching) == 1
    assert matching[0].id == original_id
    assert matching[0].is_active is False
    assert matching[0].resource_type == original_type
    assert matching[0].unit == original_unit


def test_readd_deleted_resource_is_rejected_preserving_requirements(
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
            "resource_type": "machine",
            "unit": "pcs",
        },
    )

    assert recreate_response.status_code == 409
    assert (
        recreate_response.json()["detail"]
        == DUPLICATE_INACTIVE_NAME_ERROR
    )

    # The requirement still points at the same (now inactive) row -
    # nothing was recreated, re-pointed, or reactivated.
    db.expire_all()
    db.refresh(requirement)

    assert requirement.resource_id == original_id
    assert wood.is_active is False
    assert wood.resource_type == "material"
    assert wood.unit == "kg"


def test_reactivate_resource_preserves_identity_relationships_and_cycle_values(
    client,
    db,
    optimization_cycle,
    test_product_resource_requirements,
    test_resources,
):
    wood = next(r for r in test_resources if r.name == "Test Wood")
    original_id = wood.id
    original_name = wood.name
    original_type = wood.resource_type
    original_unit = wood.unit

    requirement_snapshot = {
        requirement.id: (
            requirement.product_id,
            requirement.resource_id,
            requirement.quantity_required,
        )
        for requirement in db.query(ProductResourceRequirement)
        .filter(ProductResourceRequirement.resource_id == original_id)
        .all()
    }
    assert requirement_snapshot

    cycle_resource = (
        db.query(CycleResource)
        .filter(
            CycleResource.production_cycle_id == optimization_cycle.id,
            CycleResource.resource_id == original_id,
        )
        .one()
    )
    cycle_snapshot = (
        cycle_resource.available_quantity,
        cycle_resource.unit_price,
    )

    delete_response = client.delete(f"/api/resources/{original_id}")
    assert delete_response.status_code == 204

    reactivate_response = client.patch(
        f"/api/resources/{original_id}",
        json={"is_active": True},
    )
    assert reactivate_response.status_code == 200

    reactivated = reactivate_response.json()
    assert reactivated["id"] == original_id
    assert reactivated["name"] == original_name
    assert reactivated["resource_type"] == original_type
    assert reactivated["unit"] == original_unit
    assert reactivated["is_active"] is True

    db.expire_all()

    # The same row came back - no second resource was created.
    matching = [
        resource
        for resource in db.query(Resource).all()
        if resource.name.strip().lower()
        == original_name.strip().lower()
    ]
    assert len(matching) == 1
    assert matching[0].id == original_id

    # Product requirements still point at the same resource, with the
    # same quantities - reactivation neither rewrites nor re-points
    # them.
    persisted_requirements = (
        db.query(ProductResourceRequirement)
        .filter(ProductResourceRequirement.resource_id == original_id)
        .all()
    )
    assert {
        requirement.id: (
            requirement.product_id,
            requirement.resource_id,
            requirement.quantity_required,
        )
        for requirement in persisted_requirements
    } == requirement_snapshot

    # The production-cycle row is untouched: reactivation never
    # changes capacity or price.
    db.refresh(cycle_resource)
    assert (
        cycle_resource.available_quantity,
        cycle_resource.unit_price,
    ) == cycle_snapshot

    # The reactivated resource is selectable through the normal
    # active-only listing again.
    active_resources = client.get("/api/resources")
    assert active_resources.status_code == 200
    assert original_id in [
        item["id"] for item in active_resources.json()
    ]


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

        # Must BLOCK, not merge into the inactive row - update never
        # reuses/reactivates an existing resource by name, it only
        # rejects the conflict (as does create, since a soft-deleted
        # name can no longer be re-added).
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
    (not just the service function) - covers create-active-collision
    and create-inactive-rejection, and confirms the resources table's
    row count never grows on a rejected duplicate, for every
    case/whitespace variant of one name.
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

        # Soft-delete, then try to re-add a case-variant name - the
        # inactive row must be left untouched (not silently
        # reactivated, no second row inserted).
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

        assert readd_response.status_code == 409
        assert readd_response.json()["detail"] == (
            DUPLICATE_INACTIVE_NAME_ERROR
        )
        assert _resource_row_count(db) == count_before_readd

        # No lingering normalized-name duplicate group for this name,
        # and no reactivation of the row that was just deactivated.
        db.expire_all()
        matching = [
            r for r in db.query(Resource).all()
            if r.name.strip().lower() == "regression endpoint circular saw"
        ]
        assert len(matching) == 1
        assert matching[0].id == resource_id
        assert matching[0].is_active is False

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


def test_update_cycle_resource_allows_reduction_below_applied_consumption(
    client, db, optimization_cycle, test_resources,
):
    """
    Reducing a resource's available_quantity below what the currently
    applied allocation consumes must now succeed - the system no
    longer blocks this at write time (re-optimization is the intended
    remediation, not a write-time rejection). The applied
    ProductionAllocation rows themselves must be left completely
    untouched by this edit.
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

    original_allocations = {
        allocation.product_id: allocation.quantity
        for allocation in db.query(ProductionAllocation).filter(
            ProductionAllocation.production_cycle_id == optimization_cycle.id
        ).all()
    }
    assert original_allocations

    response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{wood.id}",
        json={"available_quantity": 500},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["available_quantity"]) == Decimal("500")

    cycle_resource = db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id,
        CycleResource.resource_id == wood.id,
    ).first()
    assert cycle_resource.available_quantity == Decimal("500.0000")

    after_allocations = {
        allocation.product_id: allocation.quantity
        for allocation in db.query(ProductionAllocation).filter(
            ProductionAllocation.production_cycle_id == optimization_cycle.id
        ).all()
    }
    assert after_allocations == original_allocations


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


def test_update_cycle_resource_labor_capacity_reduction_allowed(
    client, db, optimization_cycle, test_resources,
):
    """
    Labor was previously the one resource type still blocked on a
    capacity-reducing edit even though it's exempt from the
    positive-unit-price rule. The capacity-reduction guard is removed
    entirely now, so this must succeed too.
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

    assert response.status_code == 200
    assert Decimal(response.json()["available_quantity"]) == Decimal("100")


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


def test_update_cycle_resource_allows_zero_available_quantity(
    client, db, optimization_cycle, test_resources,
):
    """
    0 is a valid non-negative available_quantity (a resource that is
    completely out of stock this cycle) - the PATCH schema previously
    rejected it with gt=0, independent of the capacity guard.
    """

    resources_by_name = {r.name: r for r in test_resources}
    wood = resources_by_name["Test Wood"]

    response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{wood.id}",
        json={"available_quantity": 0},
    )

    assert response.status_code == 200
    assert Decimal(response.json()["available_quantity"]) == Decimal("0")


def test_update_cycle_resource_rejects_negative_available_quantity(
    client, db, optimization_cycle, test_resources,
):
    resources_by_name = {r.name: r for r in test_resources}
    wood = resources_by_name["Test Wood"]

    response = client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{wood.id}",
        json={"available_quantity": -1},
    )

    assert response.status_code == 422


# --- Permanent delete -------------------------------------------------
#
# DELETE /api/resources/{id}/permanent is a SEPARATE endpoint from
# DELETE /api/resources/{id}, which keeps its existing soft-delete
# meaning. These cover the three refusals (still active, still
# referenced by a product requirement, still referenced by a cycle
# resource) and the two things that must survive a successful delete:
# resource utilization history, and nothing else in the catalog.
#
# The referenced-resource cases matter most: both of those FKs are
# ON DELETE CASCADE in the database, so a missing guard would destroy
# product BOM lines and cycle pricing silently rather than erroring.


def test_permanent_delete_unknown_resource_returns_404(client):
    response = client.delete("/api/resources/99999999/permanent")

    assert response.status_code == 404
    assert response.json()["detail"] == "Resource not found"


def test_permanent_delete_rejects_active_resource(client, db):
    """
    An active resource must never be removed through this endpoint -
    the caller has to deactivate it first, which keeps the
    irreversible step a deliberate, separate decision.
    """
    original_count = _resource_row_count(db)

    resource_id = _create_test_resource(
        client, "Permanent Delete Active Guard",
    )

    response = client.delete(
        f"/api/resources/{resource_id}/permanent"
    )

    assert response.status_code == 409
    assert "still active" in response.json()["detail"].lower()
    assert "deactivate" in response.json()["detail"].lower()

    # Untouched: still present, still active.
    get_response = client.get(f"/api/resources/{resource_id}")

    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is True
    assert _resource_row_count(db) == original_count + 1

    db.query(Resource).filter(Resource.id == resource_id).delete()
    db.commit()


def test_permanent_delete_removes_unreferenced_inactive_resource(
    client, db,
):
    original_count = _resource_row_count(db)

    resource_id = _create_test_resource(
        client, "Permanent Delete Happy Path",
    )

    assert client.delete(
        f"/api/resources/{resource_id}"
    ).status_code == 204

    response = client.delete(
        f"/api/resources/{resource_id}/permanent"
    )

    assert response.status_code == 204

    # The row is really gone, not soft-deleted a second time.
    assert client.get(
        f"/api/resources/{resource_id}"
    ).status_code == 404

    assert (
        db.query(Resource)
        .filter(Resource.id == resource_id)
        .count()
    ) == 0

    assert _resource_row_count(db) == original_count


def test_permanent_delete_blocked_by_product_requirement_preserves_it(
    client, db,
):
    """
    The cascade regression that matters most: a bare
    db.delete(resource) would take every referencing
    ProductResourceRequirement row with it - a product BOM line - with
    no error at all. The delete must be refused and the requirement
    row must still be there afterwards.
    """
    resource_id = _create_test_resource(
        client, "Permanent Delete Requirement Guard",
    )

    product = Product(
        name="Permanent Delete Guard Product",
        selling_price=Decimal("1000.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    requirement = ProductResourceRequirement(
        product_id=product.id,
        resource_id=resource_id,
        quantity_required=Decimal("3.0000"),
    )

    db.add(requirement)
    db.commit()
    db.refresh(requirement)

    requirement_id = requirement.id

    assert client.delete(
        f"/api/resources/{resource_id}"
    ).status_code == 204

    response = client.delete(
        f"/api/resources/{resource_id}/permanent"
    )

    assert response.status_code == 409

    detail = response.json()["detail"]

    # Actionable: names the blocking product, and says the caller has
    # to clear it rather than this endpoint doing it for them.
    assert "Permanent Delete Guard Product" in detail
    assert "resource requirements" in detail.lower()

    # Nothing was destroyed - neither the BOM line nor the resource.
    assert (
        db.query(ProductResourceRequirement)
        .filter(ProductResourceRequirement.id == requirement_id)
        .count()
    ) == 1

    assert (
        db.query(Resource)
        .filter(Resource.id == resource_id)
        .count()
    ) == 1

    db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.id == requirement_id
    ).delete(synchronize_session=False)
    db.query(Product).filter(Product.id == product.id).delete()
    db.query(Resource).filter(Resource.id == resource_id).delete()
    db.commit()


def test_permanent_delete_blocked_by_cycle_resource_preserves_it(
    client, db,
):
    """
    cycle_resources.resource_id is ON DELETE CASCADE too, so the same
    guard has to cover a production cycle availability/pricing row.
    """
    resource_id = _create_test_resource(
        client, "Permanent Delete Cycle Guard",
    )

    cycle = _create_cycle(db)

    cycle_resource = CycleResource(
        production_cycle_id=cycle.id,
        resource_id=resource_id,
        available_quantity=Decimal("100.0000"),
        unit_price=Decimal("25.0000"),
    )

    db.add(cycle_resource)
    db.commit()
    db.refresh(cycle_resource)

    cycle_resource_id = cycle_resource.id

    assert client.delete(
        f"/api/resources/{resource_id}"
    ).status_code == 204

    response = client.delete(
        f"/api/resources/{resource_id}/permanent"
    )

    assert response.status_code == 409

    detail = response.json()["detail"]

    assert f"#{cycle.id}" in detail
    assert "production cycle" in detail.lower()

    assert (
        db.query(CycleResource)
        .filter(CycleResource.id == cycle_resource_id)
        .count()
    ) == 1

    assert (
        db.query(Resource)
        .filter(Resource.id == resource_id)
        .count()
    ) == 1

    _delete_cycle(db, cycle)

    db.query(Resource).filter(Resource.id == resource_id).delete()
    db.commit()


def test_permanent_delete_preserves_utilization_history(client, db):
    """
    resource_utilization_history_items.resource_id is ON DELETE SET
    NULL and every displayed field is snapshotted onto the row at
    creation time, so utilization history must NOT block the delete
    and must stay fully readable afterwards.
    """
    resource_id = _create_test_resource(
        client, "Permanent Delete History Guard",
    )

    cycle = _create_cycle(db)

    utilization_run = ResourceUtilizationRun(
        utilization_number="UT-PDEL-01",
        production_cycle_id=cycle.id,
        generated_at=datetime(2026, 8, 9),
    )

    db.add(utilization_run)
    db.commit()
    db.refresh(utilization_run)

    item = ResourceUtilizationHistoryItem(
        utilization_run_id=utilization_run.id,
        resource_id=resource_id,
        resource_name="Permanent Delete History Guard",
        resource_type="machine",
        unit="hrs",
        available_quantity=Decimal("100.0000"),
        consumed_quantity=Decimal("40.0000"),
        remaining_quantity=Decimal("60.0000"),
        utilization_rate=Decimal("40.00"),
        status="normal",
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    item_id = item.id

    assert client.delete(
        f"/api/resources/{resource_id}"
    ).status_code == 204

    # History alone does not block the delete.
    response = client.delete(
        f"/api/resources/{resource_id}/permanent"
    )

    assert response.status_code == 204

    db.expire_all()

    preserved = db.get(ResourceUtilizationHistoryItem, item_id)

    assert preserved is not None

    # The FK was nulled by the database, and every snapshotted field
    # a history view renders is intact.
    assert preserved.resource_id is None
    assert preserved.resource_name == "Permanent Delete History Guard"
    assert preserved.resource_type == "machine"
    assert preserved.unit == "hrs"
    assert preserved.available_quantity == Decimal("100.0000")
    assert preserved.consumed_quantity == Decimal("40.0000")
    assert preserved.remaining_quantity == Decimal("60.0000")
    assert preserved.utilization_rate == Decimal("40.00")
    assert preserved.status == "normal"

    _delete_cycle(db, cycle)


def test_permanent_delete_frees_the_name_for_reuse(client, db):
    """
    create_resource blocks a name held by ANY existing row, including
    a soft-deleted one (DUPLICATE_INACTIVE_NAME_ERROR). That
    reservation exists only because the soft-deleted row does, so a
    permanent delete is expected to release it - while the
    reservation itself stays intact for a merely-deactivated
    resource, which is asserted first here.
    """
    name = "Permanent Delete Name Reuse"

    resource_id = _create_test_resource(client, name)

    assert client.delete(
        f"/api/resources/{resource_id}"
    ).status_code == 204

    # Still reserved while the soft-deleted row exists - unchanged
    # existing behavior.
    blocked = client.post(
        "/api/resources",
        json={
            "name": name,
            "resource_type": "machine",
            "unit": "hrs",
        },
    )

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == DUPLICATE_INACTIVE_NAME_ERROR

    assert client.delete(
        f"/api/resources/{resource_id}/permanent"
    ).status_code == 204

    # Now free: a new resource can take the name, with a NEW id.
    recreated = client.post(
        "/api/resources",
        json={
            "name": name,
            "resource_type": "machine",
            "unit": "hrs",
        },
    )

    assert recreated.status_code == 201
    assert recreated.json()["id"] != resource_id
    assert recreated.json()["is_active"] is True

    db.query(Resource).filter(
        Resource.id == recreated.json()["id"]
    ).delete()
    db.commit()


def test_soft_delete_endpoint_still_only_deactivates(client, db):
    """
    Regression guard for the endpoint that already existed: adding the
    permanent route must not turn DELETE /api/resources/{id} into a
    real delete. Route ordering matters here - /{id}/permanent is
    registered first - so this confirms /{id} still resolves to
    deactivation.
    """
    original_count = _resource_row_count(db)

    resource_id = _create_test_resource(
        client, "Soft Delete Still Soft",
    )

    assert client.delete(
        f"/api/resources/{resource_id}"
    ).status_code == 204

    get_response = client.get(f"/api/resources/{resource_id}")

    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False

    # The row is kept, so the count still includes it.
    assert _resource_row_count(db) == original_count + 1

    db.query(Resource).filter(Resource.id == resource_id).delete()
    db.commit()
