from datetime import datetime, timezone
from decimal import Decimal

from app.database.models import (
    OptimizationResult,
    OptimizationRun,
    ProductionAllocation,
    ProductionCycle,
)
from app.services.resource_utilization import classify_utilization_status


def _allocate(db, cycle_id, product_id, quantity):
    allocation = ProductionAllocation(
        production_cycle_id=cycle_id,
        product_id=product_id,
        quantity=quantity,
    )
    db.add(allocation)
    db.commit()
    db.refresh(allocation)

    return allocation


def test_utilization_with_no_allocations_reports_zero_consumption(
    client,
    optimization_cycle,
):
    response = client.get(
        f"/api/resource-utilization/{optimization_cycle.id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["cycle_id"] == optimization_cycle.id
    assert len(data["resources"]) == 4
    assert data["bottlenecks"] == []
    assert Decimal(data["overall_utilization_rate"]) == Decimal("0.00")

    # No applied allocation: every resource is "normal", nothing is
    # at-risk, and the most-constrained resource is still reported
    # (0% utilization, but a real resource - not None) since resources
    # exist even though none has been consumed yet.
    assert data["at_risk_resources"] == []
    assert data["most_constrained_resource"] is not None
    assert Decimal(
        data["most_constrained_resource"]["utilization_rate"]
    ) == Decimal("0.00")
    assert data["material_resource_count"] == 3

    for item in data["resources"]:
        assert Decimal(item["consumed_quantity"]) == Decimal("0")
        assert Decimal(item["remaining_quantity"]) == Decimal(
            item["available_quantity"]
        )
        assert Decimal(item["utilization_rate"]) == Decimal("0.00")
        assert item["status"] == "normal"


def test_utilization_reflects_actual_allocation_consumption(
    client,
    db,
    optimization_cycle,
    test_products,
):
    products = {product.name: product for product in test_products}

    allocation = _allocate(
        db,
        optimization_cycle.id,
        products["Test Chair"].id,
        Decimal("17"),
    )

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        assert response.status_code == 200

        data = response.json()

        by_name = {
            item["resource_name"]: item
            for item in data["resources"]
        }

        expected_consumed = {
            "Test Wood": Decimal("204"),
            "Test Epoxy": Decimal("8.5"),
            "Test Nails": Decimal("2.55"),
            "Test Labor": Decimal("136"),
        }

        for name, expected_quantity in expected_consumed.items():
            item = by_name[name]

            assert Decimal(item["consumed_quantity"]) == expected_quantity

            available = Decimal(item["available_quantity"])
            remaining = Decimal(item["remaining_quantity"])

            assert remaining == available - expected_quantity

            if available > 0:
                expected_rate = (
                    expected_quantity / available * Decimal("100")
                ).quantize(Decimal("0.01"))

                assert Decimal(item["utilization_rate"]) == expected_rate

        # Epoxy capacity is 8, consumption is 8.5 -> over capacity.
        bottleneck_names = {
            bottleneck["resource_name"]
            for bottleneck in data["bottlenecks"]
        }

        assert bottleneck_names == {"Test Epoxy"}

        epoxy_bottleneck = next(
            bottleneck
            for bottleneck in data["bottlenecks"]
            if bottleneck["resource_name"] == "Test Epoxy"
        )

        assert Decimal(
            epoxy_bottleneck["shortage_quantity"]
        ) == Decimal("0.5")
        assert epoxy_bottleneck["is_binding"] is False

        # Labor and machine classification (resource_type based).
        assert Decimal(data["total_labor_hours_used"]) == Decimal("136")
        assert Decimal(
            data["total_labor_hours_capacity"]
        ) == Decimal("576")
        assert Decimal(data["total_machine_hours_used"]) == Decimal("0")
        assert Decimal(
            data["total_machine_hours_capacity"]
        ) == Decimal("0")

        expected_raw_materials = (
            expected_consumed["Test Wood"]
            + expected_consumed["Test Epoxy"]
            + expected_consumed["Test Nails"]
        )

        assert Decimal(
            data["total_raw_materials_consumed"]
        ) == expected_raw_materials

        # Overall rate is self-consistent with the returned totals.
        total_consumed = sum(
            Decimal(item["consumed_quantity"])
            for item in data["resources"]
        )
        total_available = sum(
            Decimal(item["available_quantity"])
            for item in data["resources"]
        )
        expected_overall_rate = (
            total_consumed / total_available * Decimal("100")
        ).quantize(Decimal("0.01"))

        assert Decimal(
            data["overall_utilization_rate"]
        ) == expected_overall_rate

    finally:
        db.delete(allocation)
        db.commit()


def test_utilization_unknown_cycle_returns_404(client):
    response = client.get("/api/resource-utilization/999999")

    assert response.status_code == 404


def test_utilization_default_route_uses_latest_cycle(
    client,
    db,
    optimization_cycle,
):
    newer_cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 10),
        start_date=datetime(2026, 8, 10),
        end_date=datetime(2026, 8, 10),
        status="OPEN",
    )
    db.add(newer_cycle)
    db.commit()
    db.refresh(newer_cycle)

    try:
        response = client.get("/api/resource-utilization")

        assert response.status_code == 200

        data = response.json()

        assert data["cycle_id"] == newer_cycle.id
        assert data["resources"] == []
        assert data["bottlenecks"] == []

    finally:
        db.delete(newer_cycle)
        db.commit()


def test_classify_utilization_status_thresholds():
    """
    Pure boundary test for the four-tier status classification -
    normal < 80, high 80-<90, at_risk 90-<100, bottleneck >= 100.
    """

    assert classify_utilization_status(Decimal("0")) == "normal"
    assert classify_utilization_status(Decimal("79.99")) == "normal"
    assert classify_utilization_status(Decimal("80")) == "high"
    assert classify_utilization_status(Decimal("89.99")) == "high"
    assert classify_utilization_status(Decimal("90")) == "at_risk"
    assert classify_utilization_status(Decimal("99.99")) == "at_risk"
    assert classify_utilization_status(Decimal("100")) == "bottleneck"
    assert classify_utilization_status(Decimal("150")) == "bottleneck"


def test_utilization_labor_at_99_percent_is_at_risk_not_bottleneck(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    Reproduces the exact live-verified scenario (Dining Table x11,
    Chair x7, Bed Frame x3 against the 1250/8/100/576 wood/epoxy/
    nails/labor capacities) that motivated this feature: Labor lands
    at 572/576 = 99.31% - at_risk, not a bottleneck - while Epoxy
    (6.8/8 = 85%) is "high" and Wood/Nails stay "normal". Confirms the
    new status tiers sit alongside the untouched true-bottleneck rule
    (remaining_quantity <= 0) rather than replacing it.
    """

    products = {product.name: product for product in test_products}

    allocations = [
        _allocate(
            db,
            optimization_cycle.id,
            products["Test Dining Table"].id,
            Decimal("11"),
        ),
        _allocate(
            db,
            optimization_cycle.id,
            products["Test Chair"].id,
            Decimal("7"),
        ),
        _allocate(
            db,
            optimization_cycle.id,
            products["Test Bed Frame"].id,
            Decimal("3"),
        ),
    ]

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        assert response.status_code == 200

        data = response.json()

        by_name = {
            item["resource_name"]: item
            for item in data["resources"]
        }

        labor = by_name["Test Labor"]

        assert Decimal(labor["consumed_quantity"]) == Decimal("572")
        assert Decimal(labor["utilization_rate"]) == Decimal("99.31")
        assert labor["status"] == "at_risk"

        # At_risk is NOT a bottleneck - the untouched true-bottleneck
        # rule (remaining_quantity <= 0) still governs bottlenecks[].
        assert data["bottlenecks"] == []

        at_risk_names = {
            item["resource_name"]
            for item in data["at_risk_resources"]
        }
        assert at_risk_names == {"Test Labor"}

        assert by_name["Test Epoxy"]["status"] == "high"
        assert by_name["Test Wood"]["status"] == "normal"
        assert by_name["Test Nails"]["status"] == "normal"

        # Most constrained = highest utilization_rate across all
        # resources regardless of unit (Labor 99.31 > Epoxy 85 >
        # Wood 59.52 > Nails 5.55) - not a blended cross-unit sum.
        assert (
            data["most_constrained_resource"]["resource_name"]
            == "Test Labor"
        )

        # 3 material resources (Wood/Epoxy/Nails) - Labor is its own
        # "labor" category, not material. A count, never a summed
        # cross-unit quantity.
        assert data["material_resource_count"] == 3

    finally:
        for allocation in allocations:
            db.delete(allocation)

        db.commit()


def test_utilization_status_is_bottleneck_at_exactly_100_percent(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    Epoxy consumption lands at exactly its 8-unit capacity (16 chairs
    x 0.5 epoxy each) - remaining_quantity == 0, the exact boundary of
    the pre-existing true-bottleneck rule. status must be "bottleneck"
    (not "at_risk"), and it must be excluded from at_risk_resources -
    a resource is never classified as both simultaneously.
    """

    allocation = _allocate(
        db,
        optimization_cycle.id,
        {p.name: p for p in test_products}["Test Chair"].id,
        Decimal("16"),
    )

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        data = response.json()

        epoxy = next(
            item
            for item in data["resources"]
            if item["resource_name"] == "Test Epoxy"
        )

        assert Decimal(epoxy["consumed_quantity"]) == Decimal("8")
        assert Decimal(epoxy["remaining_quantity"]) == Decimal("0")
        assert Decimal(epoxy["utilization_rate"]) == Decimal("100.00")
        assert epoxy["status"] == "bottleneck"

        at_risk_names = {
            item["resource_name"]
            for item in data["at_risk_resources"]
        }
        assert "Test Epoxy" not in at_risk_names

        bottleneck_names = {
            b["resource_name"] for b in data["bottlenecks"]
        }
        assert "Test Epoxy" in bottleneck_names

    finally:
        db.delete(allocation)
        db.commit()


def test_utilization_status_is_bottleneck_above_100_percent_with_shortage(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    17 chairs need 8.5 epoxy against an 8-unit capacity - over
    capacity, remaining_quantity < 0. status must be "bottleneck" and
    the existing shortage_quantity/is_binding fields stay correct
    (mirrors the pre-existing over-capacity assertions, extended with
    the new status field).
    """

    allocation = _allocate(
        db,
        optimization_cycle.id,
        {p.name: p for p in test_products}["Test Chair"].id,
        Decimal("17"),
    )

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        data = response.json()

        epoxy = next(
            item
            for item in data["resources"]
            if item["resource_name"] == "Test Epoxy"
        )

        assert Decimal(epoxy["remaining_quantity"]) == Decimal("-0.5")
        assert epoxy["status"] == "bottleneck"

        epoxy_bottleneck = next(
            b
            for b in data["bottlenecks"]
            if b["resource_name"] == "Test Epoxy"
        )
        assert epoxy_bottleneck["is_binding"] is False
        assert Decimal(
            epoxy_bottleneck["shortage_quantity"]
        ) == Decimal("0.5")

    finally:
        db.delete(allocation)
        db.commit()


def test_utilization_ignores_optimization_preview_without_applied_allocation(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    Resource Utilization must read applied ProductionAllocation rows
    only, never the optimizer's preview (OptimizationRun/
    OptimizationResult). Creates a preview-only optimization run/
    result for the cycle with NO corresponding ProductionAllocation,
    and confirms consumption is still reported as zero everywhere.
    """

    chair = {p.name: p for p in test_products}["Test Chair"]

    run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime.now(timezone.utc),
        status="OPTIMAL",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    result = OptimizationResult(
        optimization_run_id=run.id,
        product_id=chair.id,
        recommended_quantity=Decimal("50"),
        unit_profit=Decimal("100.0000"),
        total_profit=Decimal("5000.0000"),
    )
    db.add(result)
    db.commit()

    try:
        response = client.get(
            f"/api/resource-utilization/{optimization_cycle.id}"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["bottlenecks"] == []
        assert data["at_risk_resources"] == []

        for item in data["resources"]:
            assert Decimal(item["consumed_quantity"]) == Decimal("0")
            assert item["status"] == "normal"

    finally:
        db.delete(run)
        db.commit()
