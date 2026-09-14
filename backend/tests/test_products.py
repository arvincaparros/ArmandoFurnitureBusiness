from decimal import Decimal

from app.database.models import ProductResourceRequirement


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


def test_update_product_resource_requirement_that_would_invalidate_applied_allocation_is_rejected(
    client,
    db,
    optimization_cycle,
    test_products,
    test_resources,
    test_product_resource_requirements,
):
    """
    Applied allocation: Chair=12, Bed Frame=12 (baseline optimum, no
    minimum_demand). Wood consumption = 12*12 + 12*55 = 804, capacity
    1250. Bumping Chair's own Wood requirement from 12 to 50 pushes
    Chair's Wood need to 12*50=600, total 600+660=1260 > 1250.
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

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Wood" in detail

    requirement = db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id == chair.id,
        ProductResourceRequirement.resource_id == wood.id,
    ).first()
    assert requirement.quantity_required == Decimal("12.0000")
