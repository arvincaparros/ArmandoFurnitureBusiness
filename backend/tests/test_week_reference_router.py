def test_list_week_references(client):
    response = client.get("/api/week-references")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 8
    assert body[0]["week"] == 1
    assert body[0]["is_verified"] is True


def test_compare_week_one_exact_reference(client):
    response = client.post("/api/week-references/1/compare", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Optimal"
    assert body["is_modified_input"] is False
    assert body["reference_match_status"] == "EXACT_MATCH"
    assert body["computed_allocation"] == body["reference_allocation"]
    assert body["computed_total"] == 40


def test_compare_with_resource_override_is_flagged_and_not_blocked(client):
    response = client.post(
        "/api/week-references/1/compare",
        json={"resource_overrides": {"doorknob": "0"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_modified_input"] is True
    assert body["reference_match_status"] == "MODIFIED_INPUT"
    assert body["status"] == "Optimal"


def test_compare_includes_resource_utilization_summary(client):
    response = client.post("/api/week-references/1/compare", json={})

    assert response.status_code == 200
    body = response.json()
    usage = body["resource_usage"]

    assert float(usage["epoxy"]["available"]) == 8.0
    assert float(usage["epoxy"]["consumed"]) == 8.0
    assert float(usage["epoxy"]["remaining"]) == 0.0
    assert float(usage["epoxy"]["utilization_rate"]) == 100.0

    assert float(usage["circular_saw"]["remaining"]) == 209.0
    assert float(usage["circular_saw"]["utilization_rate"]) < 50.0


def test_compare_unknown_week_returns_404(client):
    response = client.post("/api/week-references/99/compare", json={})

    assert response.status_code == 404


def test_requires_authentication(unauthenticated_client):
    response = unauthenticated_client.get("/api/week-references")

    assert response.status_code == 401
