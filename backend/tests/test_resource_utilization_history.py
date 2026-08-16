from datetime import datetime, timezone
from decimal import Decimal

from app.database.models import (
    OptimizationResult,
    OptimizationRun,
    ProductionAllocation,
    ResourceUtilizationHistoryItem,
    ResourceUtilizationRun,
)


def _optimize(client, cycle_id):
    return client.post(
        f"/api/production-cycles/{cycle_id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )


def _apply(client, cycle_id):
    return client.post(
        f"/api/production-cycles/{cycle_id}/optimize/apply",
    )


def _seed_optimal_run(db, cycle_id, product_id, quantity):
    """
    Directly constructs an OPTIMAL OptimizationRun/OptimizationResult
    - bypassing the real PuLP solver - so a test can force an exact,
    predictable recommended_quantity for apply_optimization() to pick
    up. Calling the real /optimize endpoint instead would let the
    solver choose its own quantity (whatever maximizes profit given
    ALL constraints), which can't be pinned to an exact utilization
    percentage for a deterministic status-boundary assertion.
    """

    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=datetime.now(timezone.utc),
        status="OPTIMAL",
    )

    db.add(run)
    db.flush()

    db.add(
        OptimizationResult(
            optimization_run_id=run.id,
            product_id=product_id,
            recommended_quantity=Decimal(str(quantity)),
            unit_profit=Decimal("1.0000"),
            total_profit=Decimal(str(quantity)),
        )
    )

    db.commit()

    return run


# ---------------------------------------------------------------
# 1/2. Applying production creates history; Generate alone does not.
# ---------------------------------------------------------------

def test_apply_creates_resource_utilization_history(
    client,
    db,
    optimization_cycle,
    test_products,
):
    optimize_response = _optimize(client, optimization_cycle.id)
    assert optimize_response.status_code == 200

    # Generate-only: no history yet.
    assert (
        db.query(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )

    apply_response = _apply(client, optimization_cycle.id)
    assert apply_response.status_code == 200

    runs = (
        db.query(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    assert len(runs) == 1
    assert runs[0].utilization_number.startswith("UT-")


def test_generate_without_apply_creates_no_history(
    client,
    db,
    optimization_cycle,
    test_products,
):
    response = _optimize(client, optimization_cycle.id)
    assert response.status_code == 200

    assert db.query(ResourceUtilizationRun).filter(
        ResourceUtilizationRun.production_cycle_id
        == optimization_cycle.id
    ).count() == 0

    # Scoped to this cycle's own run(s), not an unfiltered count - the
    # shared dev database this test suite runs against may contain
    # real ResourceUtilizationHistoryItem rows from other cycles.
    assert (
        db.query(ResourceUtilizationHistoryItem)
        .join(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


# ---------------------------------------------------------------
# 3. One detail record per resource.
# ---------------------------------------------------------------

def test_one_history_item_per_resource(
    client,
    db,
    optimization_cycle,
    test_products,
):
    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    run = (
        db.query(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .one()
    )

    # optimization_cycle fixture configures exactly 4 CycleResource
    # rows (Test Wood/Epoxy/Nails/Labor) - see conftest.py.
    assert len(run.items) == 4

    item_names = {item.resource_name for item in run.items}
    assert item_names == {
        "Test Wood", "Test Epoxy", "Test Nails", "Test Labor",
    }


# ---------------------------------------------------------------
# 4/5/6/7. Snapshotted values match a manual recomputation from the
# actual persisted ProductionAllocation x ProductResourceRequirement.
# ---------------------------------------------------------------

def test_history_values_match_allocation_based_calculation(
    client,
    db,
    optimization_cycle,
    test_products,
):
    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    allocations = (
        db.query(ProductionAllocation)
        .filter(
            ProductionAllocation.production_cycle_id
            == optimization_cycle.id
        )
        .all()
    )

    assert len(allocations) > 0

    # Independently recompute expected Wood consumption from the
    # actual persisted allocations x each product's known
    # requirement (see conftest.py::test_product_resource_requirements)
    # - Dining Table wood=45, Chair wood=12, Bed Frame wood=55.
    wood_per_unit = {
        "Test Dining Table": Decimal("45.0000"),
        "Test Chair": Decimal("12.0000"),
        "Test Bed Frame": Decimal("55.0000"),
    }

    products_by_id = {
        product.id: product for product in test_products
    }

    expected_wood_consumed = sum(
        (
            wood_per_unit[products_by_id[a.product_id].name]
            * a.quantity
            for a in allocations
        ),
        Decimal("0"),
    )

    run = (
        db.query(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .one()
    )

    wood_item = next(
        item for item in run.items
        if item.resource_name == "Test Wood"
    )

    assert wood_item.consumed_quantity == expected_wood_consumed
    assert wood_item.available_quantity == Decimal("1250.0000")
    assert wood_item.remaining_quantity == (
        Decimal("1250.0000") - expected_wood_consumed
    )

    expected_rate = (
        expected_wood_consumed
        / Decimal("1250.0000")
        * Decimal("100")
    ).quantize(Decimal("0.01"))

    assert wood_item.utilization_rate == expected_rate


# ---------------------------------------------------------------
# 8/9. Status snapshotted correctly for bottleneck / at_risk.
# ---------------------------------------------------------------

def test_history_status_bottleneck_at_exactly_100_percent(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    16 Test Chairs consume exactly 8kg of Epoxy (0.5/unit) against an
    8kg capacity - a legitimate, fully-exhausted bottleneck, not an
    over-allocation. Uses _seed_optimal_run() rather than the real
    /optimize endpoint so this exact quantity is guaranteed, not
    whatever the solver happens to pick.
    """

    from app.services.optimization import apply_optimization

    chair = next(
        p for p in test_products if p.name == "Test Chair"
    )

    _seed_optimal_run(
        db, optimization_cycle.id, chair.id, "16",
    )

    apply_optimization(db, optimization_cycle.id)

    run = (
        db.query(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .order_by(ResourceUtilizationRun.id.desc())
        .first()
    )

    epoxy_item = next(
        item for item in run.items
        if item.resource_name == "Test Epoxy"
    )

    assert epoxy_item.utilization_rate == Decimal("100.00")
    assert epoxy_item.status == "bottleneck"


def test_history_status_at_risk_between_90_and_100_percent(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """15 Test Chairs x 0.5 epoxy = 7.5 / 8.0 = 93.75% - squarely in
    the 90-<100 at_risk band."""

    from app.services.optimization import apply_optimization

    chair = next(
        p for p in test_products if p.name == "Test Chair"
    )

    _seed_optimal_run(
        db, optimization_cycle.id, chair.id, "15",
    )

    apply_optimization(db, optimization_cycle.id)

    run = (
        db.query(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .order_by(ResourceUtilizationRun.id.desc())
        .first()
    )

    epoxy_item = next(
        item for item in run.items
        if item.resource_name == "Test Epoxy"
    )

    assert epoxy_item.utilization_rate == Decimal("93.75")
    assert epoxy_item.status == "at_risk"


# ---------------------------------------------------------------
# 10. History does not change after current CycleResource changes.
# ---------------------------------------------------------------

def test_history_is_immutable_after_cycle_resource_changes(
    client,
    db,
    optimization_cycle,
    test_products,
):
    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    run = (
        db.query(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .one()
    )

    wood_item = next(
        item for item in run.items
        if item.resource_name == "Test Wood"
    )

    original_consumed = wood_item.consumed_quantity
    original_remaining = wood_item.remaining_quantity
    original_rate = wood_item.utilization_rate

    # Change the CURRENT/live availability drastically.
    from app.database.models import CycleResource

    cycle_resource = (
        db.query(CycleResource)
        .filter(
            CycleResource.production_cycle_id
            == optimization_cycle.id,
            CycleResource.resource_id == wood_item.resource_id,
        )
        .one()
    )

    cycle_resource.available_quantity = Decimal("999999.0000")
    db.commit()

    db.refresh(wood_item)

    assert wood_item.consumed_quantity == original_consumed
    assert wood_item.remaining_quantity == original_remaining
    assert wood_item.utilization_rate == original_rate
    assert wood_item.available_quantity != Decimal("999999.0000")


# ---------------------------------------------------------------
# 11. Failed apply does not create partial utilization history.
# ---------------------------------------------------------------

def test_failed_apply_creates_no_partial_history(
    client,
    db,
    optimization_cycle,
):
    """No OptimizationRun exists for this cycle - apply must fail
    before ever reaching the utilization-snapshot step."""

    response = _apply(client, optimization_cycle.id)

    assert response.status_code == 400
    assert (
        db.query(ResourceUtilizationRun)
        .filter(
            ResourceUtilizationRun.production_cycle_id
            == optimization_cycle.id
        )
        .count()
        == 0
    )


# ---------------------------------------------------------------
# 12. History endpoints return the expected data.
# ---------------------------------------------------------------

def test_history_list_endpoint(
    client,
    optimization_cycle,
    test_products,
):
    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    response = client.get(
        "/api/resource-utilization/history",
        params={"cycle_id": optimization_cycle.id},
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["utilization_number"].startswith("UT-")
    assert body[0]["production_cycle_id"] == optimization_cycle.id
    assert body[0]["resource_count"] == 4
    assert "bottleneck_count" in body[0]
    assert "at_risk_count" in body[0]
    # Summary view intentionally omits per-resource detail.
    assert "items" not in body[0]


def test_history_detail_endpoint(
    client,
    optimization_cycle,
    test_products,
):
    _optimize(client, optimization_cycle.id)
    _apply(client, optimization_cycle.id)

    list_response = client.get(
        "/api/resource-utilization/history",
        params={"cycle_id": optimization_cycle.id},
    )

    run_id = list_response.json()[0]["id"]

    response = client.get(
        f"/api/resource-utilization/history/{run_id}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == run_id
    assert len(body["items"]) == 4

    for item in body["items"]:
        assert "resource_name" in item
        assert "consumed_quantity" in item
        assert "remaining_quantity" in item
        assert "utilization_rate" in item
        assert "status" in item


def test_history_detail_endpoint_unknown_id_returns_404(client):
    response = client.get(
        "/api/resource-utilization/history/999999"
    )

    assert response.status_code == 404


def test_history_list_route_not_shadowed_by_cycle_id_route(client):
    """
    /history must resolve to the history endpoint, not be swallowed
    by GET /{cycle_id}'s int path param (which would 422 on the
    literal string "history") - mirrors the exact /latest ordering
    fix already applied elsewhere in this codebase
    (production.py's /latest route).
    """

    response = client.get("/api/resource-utilization/history")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
