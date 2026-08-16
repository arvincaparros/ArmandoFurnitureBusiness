from decimal import Decimal


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
