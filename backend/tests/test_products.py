from decimal import Decimal

from sqlalchemy import select

from app.database.models import (
    ProductionApplication,
    ProductionApplicationResourceItem,
    ProductResourceRequirement,
)


def test_list_products_returns_only_active_by_default(client, test_products, db):
    inactive = test_products[0]
    inactive.is_active = False
    db.commit()

    response = client.get("/api/products")

    assert response.status_code == 200

    names = [item["name"] for item in response.json()]

    assert inactive.name not in names
    assert test_products[1].name in names


def test_list_products_include_inactive(client, test_products, db):
    inactive = test_products[0]
    inactive.is_active = False
    db.commit()

    response = client.get(
        "/api/products",
        params={"include_inactive": True},
    )

    assert response.status_code == 200

    names = [item["name"] for item in response.json()]

    assert inactive.name in names


def test_list_products_response_fields(client, test_products):
    response = client.get("/api/products")

    assert response.status_code == 200

    item = response.json()[0]

    assert set(item.keys()) == {
        "id",
        "name",
        "selling_price",
        "labor_cost",
        "minimum_demand",
        "is_active",
    }


def test_get_product_by_id(client, test_products):
    product = test_products[0]

    response = client.get(f"/api/products/{product.id}")

    assert response.status_code == 200
    assert response.json()["name"] == product.name


def test_get_product_not_found(client):
    response = client.get("/api/products/999999")

    assert response.status_code == 404


def test_create_update_delete_product(client, cleanup_test_data):
    create_response = client.post(
        "/api/products",
        json={
            "name": "Test Dining Table",
            "selling_price": "12500.00",
            "labor_cost": "500.00",
        },
    )

    assert create_response.status_code == 201
    assert create_response.json()["labor_cost"] == "500.00"

    product_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/products/{product_id}",
        json={"selling_price": "13000.00"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["selling_price"] == "13000.00"
    # Unset in the PATCH payload - must stay unchanged, not reset.
    assert update_response.json()["labor_cost"] == "500.00"

    delete_response = client.delete(f"/api/products/{product_id}")

    assert delete_response.status_code == 204

    get_response = client.get(f"/api/products/{product_id}")

    assert get_response.status_code == 200
    assert get_response.json()["is_active"] is False


# --- minimum_demand through the Products API --------------------------
#
# The column, its migration (fa69029d2755) and the optimizer's use of
# it already existed and are covered by tests/test_minimum_demand.py.
# These tests cover only what the Product Data Management revision
# added: writing it through create/update. Nothing here touches the
# optimizer or optimization history.


def test_create_product_with_minimum_demand(client, cleanup_test_data):
    response = client.post(
        "/api/products",
        json={
            "name": "Test Minimum Demand Product",
            "selling_price": "5000.00",
            "labor_cost": "250.00",
            "minimum_demand": 4,
        },
    )

    assert response.status_code == 201
    assert response.json()["minimum_demand"] == "4.0000"


def test_create_product_without_minimum_demand_defaults_to_zero(
    client,
    cleanup_test_data,
):
    """
    Regression guard for every existing caller (the frontend's own
    create flow included) that omits the field - it must stay a 201
    defaulting to 0, never a 422.
    """

    response = client.post(
        "/api/products",
        json={
            "name": "Test Minimum Demand Product",
            "selling_price": "5000.00",
            "labor_cost": "250.00",
        },
    )

    assert response.status_code == 201
    assert response.json()["minimum_demand"] == "0.0000"


def test_update_product_minimum_demand(client, cleanup_test_data):
    create_response = client.post(
        "/api/products",
        json={
            "name": "Test Minimum Demand Product",
            "selling_price": "5000.00",
            "labor_cost": "250.00",
            "minimum_demand": 2,
        },
    )

    assert create_response.status_code == 201

    product_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/products/{product_id}",
        json={"minimum_demand": 7},
    )

    assert update_response.status_code == 200
    assert update_response.json()["minimum_demand"] == "7.0000"

    get_response = client.get(f"/api/products/{product_id}")

    assert get_response.json()["minimum_demand"] == "7.0000"


def test_update_product_minimum_demand_to_zero(client, cleanup_test_data):
    """
    0 is a real value ("no minimum"), not an absent one - an explicit
    0 must persist rather than being treated as unset and silently
    leaving the previous minimum in place.
    """

    create_response = client.post(
        "/api/products",
        json={
            "name": "Test Minimum Demand Product",
            "selling_price": "5000.00",
            "labor_cost": "250.00",
            "minimum_demand": 5,
        },
    )

    assert create_response.status_code == 201

    product_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/products/{product_id}",
        json={"minimum_demand": 0},
    )

    assert update_response.status_code == 200
    assert update_response.json()["minimum_demand"] == "0.0000"


def test_update_other_field_preserves_minimum_demand(
    client,
    cleanup_test_data,
):
    create_response = client.post(
        "/api/products",
        json={
            "name": "Test Minimum Demand Product",
            "selling_price": "5000.00",
            "labor_cost": "250.00",
            "minimum_demand": 3,
        },
    )

    assert create_response.status_code == 201

    product_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/products/{product_id}",
        json={"selling_price": "5500.00"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["selling_price"] == "5500.00"
    # Unset in the PATCH payload - must stay unchanged, not reset.
    assert update_response.json()["minimum_demand"] == "3.0000"


def test_create_product_rejects_negative_minimum_demand(
    client,
    cleanup_test_data,
):
    response = client.post(
        "/api/products",
        json={
            "name": "Test Minimum Demand Product",
            "selling_price": "5000.00",
            "labor_cost": "250.00",
            "minimum_demand": -1,
        },
    )

    assert response.status_code == 422


def test_create_product_rejects_fractional_minimum_demand(
    client,
    cleanup_test_data,
):
    response = client.post(
        "/api/products",
        json={
            "name": "Test Minimum Demand Product",
            "selling_price": "5000.00",
            "labor_cost": "250.00",
            "minimum_demand": 2.5,
        },
    )

    assert response.status_code == 422


def test_create_product_rejects_minimum_demand_above_maximum(
    client,
    cleanup_test_data,
):
    response = client.post(
        "/api/products",
        json={
            "name": "Test Minimum Demand Product",
            "selling_price": "5000.00",
            "labor_cost": "250.00",
            "minimum_demand": 1000001,
        },
    )

    assert response.status_code == 422


def test_update_product_rejects_negative_minimum_demand(
    client,
    test_products,
    db,
):
    product = test_products[0]
    original = product.minimum_demand

    response = client.patch(
        f"/api/products/{product.id}",
        json={"minimum_demand": -5},
    )

    assert response.status_code == 422

    db.refresh(product)

    assert product.minimum_demand == original


def test_update_product_rejects_fractional_minimum_demand(
    client,
    test_products,
    db,
):
    product = test_products[0]
    original = product.minimum_demand

    response = client.patch(
        f"/api/products/{product.id}",
        json={"minimum_demand": 1.25},
    )

    assert response.status_code == 422

    db.refresh(product)

    assert product.minimum_demand == original


def test_product_resource_requirements_endpoint(
    client,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    product = test_products[0]

    response = client.get(f"/api/products/{product.id}/resources")

    assert response.status_code == 200

    items = response.json()

    assert len(items) > 0

    for item in items:
        assert item["product_id"] == product.id
        assert "resource_id" in item
        assert "quantity_required" in item


def test_update_product_resource_requirement_within_capacity_is_accepted(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    chair = products_by_name["Test Chair"]
    wood = resources_by_name["Test Wood"]

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    response = client.patch(
        f"/api/products/{chair.id}/resources/{wood.id}",
        json={"quantity_required": 13},
    )

    assert response.status_code == 200


def test_update_product_resource_requirement_succeeds_even_when_it_would_invalidate_applied_allocation(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    Approved business-rule change: editing a product's resource
    requirements must never be blocked by an existing applied
    allocation's capacity, regardless of direction or size. Applied
    allocation: Chair=12, Bed Frame=12 (baseline optimum, no
    minimum_demand). Wood consumption = 12*12 + 12*55 = 804, capacity
    1250. Bumping Chair's own Wood requirement from 12 to 50 pushes
    Chair's Wood need to 12*50=600, total 600+660=1260 > 1250 - this
    must still succeed.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    chair = products_by_name["Test Chair"]
    wood = resources_by_name["Test Wood"]

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )
    assert optimize_response.status_code == 200

    apply_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    )
    assert apply_response.status_code == 200

    response = client.patch(
        f"/api/products/{chair.id}/resources/{wood.id}",
        json={"quantity_required": 50},
    )

    assert response.status_code == 200, response.text

    requirement = db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == chair.id,
        ProductResourceRequirement.resource_id == wood.id,
    ).first()
    assert requirement.quantity_required == Decimal("50.0000")


# --- Scoped-to-the-edited-resource regression tests ---------------
#
# Baseline for all of these (see the two tests above): applying with
# no minimum_demand produces Chair=12, Bed Frame=12. At the fixture's
# per-unit requirements that means, BEFORE any edit:
#   Wood:   12*12 (chair) + 12*55 (bed frame) = 804  of 1250 capacity
#   Labor:  12*8  (chair) + 12*40 (bed frame) = 576  of 576  capacity
#   Nails:  12*0.15(chair) + 12*0.4 (bed frame) = 6.6 of 100 capacity


def test_editing_an_unrelated_resource_succeeds_despite_another_resource_over_capacity(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    The regression this fix exists for: Labor already sits exactly at
    its 576 capacity before any edit. Reducing it below what is
    already applied (allowed by design - see
    test_update_cycle_resource_allows_reduction_below_applied_
    consumption) pushes Labor over capacity for reasons that have
    nothing to do with Wood. Editing Bed Frame's Wood requirement -
    a completely different resource, whose own math never changed -
    must still succeed.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    bed_frame = products_by_name["Test Bed Frame"]
    wood = resources_by_name["Test Wood"]
    labor = resources_by_name["Test Labor"]

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    ).status_code == 200

    # Push Labor over capacity - 576 already applied, 500 now declared.
    assert client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{labor.id}",
        json={"available_quantity": 500},
    ).status_code == 200

    # Wood (55 -> 20) is a reduction, and Wood's own capacity was
    # never remotely at risk (804 of 1250 before the edit).
    response = client.patch(
        f"/api/products/{bed_frame.id}/resources/{wood.id}",
        json={"quantity_required": 20},
    )

    assert response.status_code == 200, response.text

    requirement = db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == bed_frame.id,
        ProductResourceRequirement.resource_id == wood.id,
    ).first()
    assert requirement.quantity_required == Decimal("20.0000")


def test_editing_an_unrelated_resource_succeeds_despite_two_other_resources_over_capacity(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    Same mechanism as above, with TWO different already-over-capacity
    resources at once (Labor and Nails), proving the fix filters by
    the one resource actually being edited rather than merely picking
    the first shortage it happens to see.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    chair = products_by_name["Test Chair"]
    wood = resources_by_name["Test Wood"]
    labor = resources_by_name["Test Labor"]
    nails = resources_by_name["Test Nails"]

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    ).status_code == 200

    assert client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{labor.id}",
        json={"available_quantity": 500},
    ).status_code == 200

    # Nails: 6.6 already applied, now declared below that too.
    assert client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{nails.id}",
        json={"available_quantity": 5},
    ).status_code == 200

    # Wood (12 -> 15) for Chair: an increase, but nowhere near Wood's
    # own 1250 capacity (new total 180 + 660 = 840), and touches
    # neither Labor nor Nails at all.
    response = client.patch(
        f"/api/products/{chair.id}/resources/{wood.id}",
        json={"quantity_required": 15},
    )

    assert response.status_code == 200, response.text

    requirement = db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == chair.id,
        ProductResourceRequirement.resource_id == wood.id,
    ).first()
    assert requirement.quantity_required == Decimal("15.0000")


def test_increasing_the_edited_resource_past_its_own_capacity_now_succeeds(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    Approved business-rule change: an increase that pushes WOOD
    itself (the resource being edited) over its own capacity, with
    ANOTHER resource (Labor) also already over capacity, must still
    succeed - requirement editing is never blocked by capacity in
    either direction, for any resource, applied or not.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    chair = products_by_name["Test Chair"]
    wood = resources_by_name["Test Wood"]
    labor = resources_by_name["Test Labor"]

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    ).status_code == 200

    # Labor over capacity too, same as the tests above - proves the
    # success below is not conditional on any other resource's state.
    assert client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{labor.id}",
        json={"available_quantity": 500},
    ).status_code == 200

    # Chair's Wood 12 -> 50: new Wood total = 50*12 + 55*12 = 1260,
    # over the 1250 capacity by 10 - still accepted.
    response = client.patch(
        f"/api/products/{chair.id}/resources/{wood.id}",
        json={"quantity_required": 50},
    )

    assert response.status_code == 200, response.text

    requirement = db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == chair.id,
        ProductResourceRequirement.resource_id == wood.id,
    ).first()
    assert requirement.quantity_required == Decimal("50.0000")


def test_reducing_the_edited_resource_back_within_its_own_capacity_succeeds(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    Wood itself is pushed over capacity (not a different resource this
    time), then the edit REDUCES Wood's own requirement enough to fit
    again - this must succeed, proving the fix still correctly
    protects (and un-blocks) the resource actually being edited.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    bed_frame = products_by_name["Test Bed Frame"]
    wood = resources_by_name["Test Wood"]

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    ).status_code == 200

    # Wood: 804 already applied, now declared below that.
    assert client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{wood.id}",
        json={"available_quantity": 700},
    ).status_code == 200

    # Bed Frame's Wood 55 -> 20: new Wood total = 12*12 + 20*12 = 384,
    # comfortably back within the now-lowered 700 capacity.
    response = client.patch(
        f"/api/products/{bed_frame.id}/resources/{wood.id}",
        json={"quantity_required": 20},
    )

    assert response.status_code == 200, response.text

    requirement = db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == bed_frame.id,
        ProductResourceRequirement.resource_id == wood.id,
    ).first()
    assert requirement.quantity_required == Decimal("20.0000")


def test_requirement_edit_never_touches_persisted_application_history(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    Requirement #5: a requirement edit must never modify an existing
    ProductionApplication's recorded resource consumption. The ledger
    snapshot taken at apply time is what the whole engagement's
    capacity-integrity model is built on - it must still read exactly
    what it did immediately after apply, even after a later,
    successful requirement edit.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    bed_frame = products_by_name["Test Bed Frame"]
    wood = resources_by_name["Test Wood"]
    labor = resources_by_name["Test Labor"]

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    ).status_code == 200

    application = db.scalars(
        select(ProductionApplication).where(
            ProductionApplication.production_cycle_id
            == optimization_cycle.id
        )
    ).one()

    wood_consumed_before = db.scalars(
        select(ProductionApplicationResourceItem.consumed_quantity).where(
            ProductionApplicationResourceItem.production_application_id
            == application.id,
            ProductionApplicationResourceItem.resource_id == wood.id,
        )
    ).one()

    assert wood_consumed_before == Decimal("804.0000")

    assert client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{labor.id}",
        json={"available_quantity": 500},
    ).status_code == 200

    assert client.patch(
        f"/api/products/{bed_frame.id}/resources/{wood.id}",
        json={"quantity_required": 20},
    ).status_code == 200

    db.expire_all()

    wood_consumed_after = db.scalars(
        select(ProductionApplicationResourceItem.consumed_quantity).where(
            ProductionApplicationResourceItem.production_application_id
            == application.id,
            ProductionApplicationResourceItem.resource_id == wood.id,
        )
    ).one()

    assert wood_consumed_after == wood_consumed_before == Decimal(
        "804.0000"
    )


# --- Approved business-rule change: free-form requirement editing ----
#
# A product's resource requirements (its BOM) can be edited, removed,
# replaced, or added to at will, regardless of any currently applied
# ProductionAllocation or that allocation's resource capacity. See
# product_resource_requirement.py::update_product_resource_requirement.


def test_delete_resource_requirement_succeeds_despite_over_capacity_allocation(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    chair = products_by_name["Test Chair"]
    wood = resources_by_name["Test Wood"]
    labor = resources_by_name["Test Labor"]

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    ).status_code == 200

    # Push Labor over capacity on the already-applied allocation.
    assert client.patch(
        f"/api/production-cycles/{optimization_cycle.id}/resources/{labor.id}",
        json={"available_quantity": 500},
    ).status_code == 200

    response = client.delete(
        f"/api/products/{chair.id}/resources/{wood.id}"
    )

    assert response.status_code == 204

    assert db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == chair.id,
        ProductResourceRequirement.resource_id == wood.id,
    ).first() is None


def test_removing_all_resource_requirements_for_a_product_succeeds(
    client,
    db,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    existing = db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == chair.id,
    ).all()

    assert existing, "fixture must give Test Chair requirements"

    for requirement in existing:
        response = client.delete(
            f"/api/products/{chair.id}/resources/{requirement.resource_id}"
        )
        assert response.status_code == 204

    assert client.get(
        f"/api/products/{chair.id}/resources"
    ).json() == []


def test_adding_a_new_requirement_after_removing_all_existing_ones_succeeds(
    client,
    db,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )
    resources_by_name = {r.name: r for r in test_resources}

    for requirement in db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == chair.id,
    ).all():
        assert client.delete(
            f"/api/products/{chair.id}/resources/{requirement.resource_id}"
        ).status_code == 204

    response = client.post(
        f"/api/products/{chair.id}/resources",
        json={
            "resource_id": resources_by_name["Test Epoxy"].id,
            "quantity_required": 3,
        },
    )

    assert response.status_code == 201, response.text

    requirements = client.get(
        f"/api/products/{chair.id}/resources"
    ).json()

    assert len(requirements) == 1
    assert requirements[0]["resource_id"] == (
        resources_by_name["Test Epoxy"].id
    )
    assert Decimal(
        requirements[0]["quantity_required"]
    ) == Decimal("3.0000")


def test_replacing_all_requirements_with_a_new_set_succeeds(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    The full "completely replace the BOM" workflow students need:
    apply a plan first, then delete every existing requirement for a
    product and add a brand new set - even though the OLD set still
    has an applied allocation on record for this cycle.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    bed_frame = products_by_name["Test Bed Frame"]

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply"
    ).status_code == 200

    for requirement in db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == bed_frame.id,
    ).all():
        assert client.delete(
            f"/api/products/{bed_frame.id}/resources/{requirement.resource_id}"
        ).status_code == 204

    new_set = {
        "Test Wood": 30,
        "Test Epoxy": 1,
        "Test Nails": 0.5,
    }

    for resource_name, quantity in new_set.items():
        response = client.post(
            f"/api/products/{bed_frame.id}/resources",
            json={
                "resource_id": resources_by_name[resource_name].id,
                "quantity_required": quantity,
            },
        )
        assert response.status_code == 201, response.text

    requirements = client.get(
        f"/api/products/{bed_frame.id}/resources"
    ).json()

    assert len(requirements) == len(new_set)

    by_resource_id = {
        item["resource_id"]: Decimal(item["quantity_required"])
        for item in requirements
    }

    for resource_name, quantity in new_set.items():
        assert by_resource_id[
            resources_by_name[resource_name].id
        ] == Decimal(str(quantity))


def test_updated_requirement_is_used_by_the_next_generate(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    Requirement #7: the very next Generate must use the NEW
    requirement value, not whatever was true the last time it ran.
    ProductResourceRequirement is read fresh from the database on
    every /optimize call (get_optimization_data), never cached or
    snapshotted at apply time, so this holds with no production code
    change - pinned here as a regression guard.
    """

    products_by_name = {p.name: p for p in test_products}
    resources_by_name = {r.name: r for r in test_resources}
    chair = products_by_name["Test Chair"]
    bed_frame = products_by_name["Test Bed Frame"]
    wood = resources_by_name["Test Wood"]

    assert client.patch(
        f"/api/products/{chair.id}/resources/{wood.id}",
        json={"quantity_required": 20},
    ).status_code == 200

    response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert response.status_code == 200

    payload = response.json()

    chair_quantity = next(
        Decimal(str(item["quantity"]))
        for item in payload["allocations"]
        if item["product_id"] == chair.id
    )
    bed_frame_quantity = next(
        Decimal(str(item["quantity"]))
        for item in payload["allocations"]
        if item["product_id"] == bed_frame.id
    )

    wood_usage = next(
        item for item in payload["resource_usage"]
        if item["resource_name"] == "Test Wood"
    )

    # Wood's required_quantity must reflect the NEW per-unit rate (20)
    # for Chair's share - Bed Frame's own Wood requirement (55/unit)
    # is untouched by this edit and folds into the same total.
    expected_required = (
        chair_quantity * Decimal("20")
        + bed_frame_quantity * Decimal("55")
    )

    assert Decimal(wood_usage["required_quantity"]) == expected_required


def test_create_duplicate_resource_requirement_is_still_rejected(
    client,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )
    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    response = client.post(
        f"/api/products/{chair.id}/resources",
        json={"resource_id": wood.id, "quantity_required": 10},
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_create_resource_requirement_for_missing_resource_is_still_rejected(
    client,
    test_products,
):
    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    response = client.post(
        f"/api/products/{chair.id}/resources",
        json={"resource_id": 999999, "quantity_required": 10},
    )

    assert response.status_code == 400
    assert "resource not found" in response.json()["detail"].lower()


def test_create_resource_requirement_for_missing_product_is_still_rejected(
    client,
    test_resources,
):
    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    response = client.post(
        "/api/products/999999/resources",
        json={"resource_id": wood.id, "quantity_required": 10},
    )

    assert response.status_code == 400
    assert "product not found" in response.json()["detail"].lower()


def test_update_resource_requirement_still_rejects_a_non_positive_quantity(
    client,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )
    wood = next(
        resource for resource in test_resources
        if resource.name == "Test Wood"
    )

    response = client.patch(
        f"/api/products/{chair.id}/resources/{wood.id}",
        json={"quantity_required": 0},
    )

    assert response.status_code == 422
