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
