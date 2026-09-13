from decimal import Decimal

from app.database.models import (
    CycleResource,
    ProductionAllocation,
)

from app.services.allocation import (
    get_allocations_with_financials,
)


def _create_allocation(db, cycle_id, product_id, quantity):
    allocation = ProductionAllocation(
        production_cycle_id=cycle_id,
        product_id=product_id,
        quantity=quantity,
    )

    db.add(allocation)
    db.commit()
    db.refresh(allocation)

    return allocation


def _delete_allocation(db, allocation):
    db.delete(allocation)
    db.commit()


def test_committed_allocation_financials_reconcile_with_current_prices(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Revision #2: for a fully-priced, fully-active product, the
    financial breakdown must match Row Total Cost =
    quantity x per-unit cost, Row Total Revenue = quantity x selling
    price, Row Total Profit = revenue - cost - using the exact same
    resource prices calculate_unit_profit() would use, just computed
    independently on the allocation read path (not by calling that
    function - see get_allocations_with_financials's docstring).
    """

    products = {product.name: product for product in test_products}
    chair = products["Test Chair"]

    allocation = _create_allocation(
        db,
        optimization_cycle.id,
        chair.id,
        Decimal("3.0000"),
    )

    try:
        results = get_allocations_with_financials(
            db,
            optimization_cycle.id,
        )

        row = next(
            item for item in results if item["product_id"] == chair.id
        )

        # Test Chair requires: Wood 12kg @84, Epoxy 0.5kg @650,
        # Nails 0.15kg @120 (all non-labor), Labor 8hrs (excluded from
        # resource cost - product.labor_cost is 0.00 for all test
        # products per conftest.py::test_products).
        expected_unit_cost = (
            Decimal("12.0000") * Decimal("84.0000")
            + Decimal("0.5000") * Decimal("650.0000")
            + Decimal("0.1500") * Decimal("120.0000")
        )

        expected_revenue = chair.selling_price * Decimal("3.0000")
        expected_cost = expected_unit_cost * Decimal("3.0000")
        expected_profit = expected_revenue - expected_cost

        assert row["quantity"] == Decimal("3.0000")
        assert row["total_revenue"] == expected_revenue
        assert row["total_cost"] == expected_cost
        assert row["total_profit"] == expected_profit
        assert (
            row["total_profit"]
            == row["total_revenue"] - row["total_cost"]
        )

    finally:
        _delete_allocation(db, allocation)


def test_committed_allocation_cost_unavailable_when_resource_inactive(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Decision 3 (Revision #2): a committed product whose required
    non-labor resource is currently inactive must report Total Cost/
    Total Profit as unavailable (None) - never silently treated as
    zero cost - while Total Revenue stays computable from
    selling_price alone.
    """

    products = {product.name: product for product in test_products}
    resources = {
        resource.name: resource for resource in test_resources
    }

    chair = products["Test Chair"]
    nails = resources["Test Nails"]

    nails.is_active = False
    db.commit()

    allocation = _create_allocation(
        db,
        optimization_cycle.id,
        chair.id,
        Decimal("3.0000"),
    )

    try:
        results = get_allocations_with_financials(
            db,
            optimization_cycle.id,
        )

        row = next(
            item for item in results if item["product_id"] == chair.id
        )

        assert row["quantity"] == Decimal("3.0000")
        assert row["total_revenue"] == (
            chair.selling_price * Decimal("3.0000")
        )
        assert row["total_cost"] is None
        assert row["total_profit"] is None

    finally:
        _delete_allocation(db, allocation)
        nails.is_active = True
        db.commit()


def test_committed_allocation_cost_unavailable_when_resource_unpriced_this_cycle(
    db,
    optimization_cycle,
    test_products,
    test_resources,
):
    """
    Same unavailable convention as the inactive-resource case, but
    triggered by this cycle simply having no CycleResource price for a
    required (still-active) resource - e.g. it was never priced for
    this cycle, distinct from Revision #1's soft-delete lifecycle.
    """

    products = {product.name: product for product in test_products}
    resources = {
        resource.name: resource for resource in test_resources
    }

    chair = products["Test Chair"]
    nails = resources["Test Nails"]

    cycle_resource = db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id,
        CycleResource.resource_id == nails.id,
    ).first()

    removed_available_quantity = cycle_resource.available_quantity
    removed_unit_price = cycle_resource.unit_price

    db.delete(cycle_resource)
    db.commit()

    allocation = _create_allocation(
        db,
        optimization_cycle.id,
        chair.id,
        Decimal("3.0000"),
    )

    try:
        results = get_allocations_with_financials(
            db,
            optimization_cycle.id,
        )

        row = next(
            item for item in results if item["product_id"] == chair.id
        )

        assert row["total_revenue"] == (
            chair.selling_price * Decimal("3.0000")
        )
        assert row["total_cost"] is None
        assert row["total_profit"] is None

    finally:
        _delete_allocation(db, allocation)

        db.add(
            CycleResource(
                production_cycle_id=optimization_cycle.id,
                resource_id=nails.id,
                available_quantity=removed_available_quantity,
                unit_price=removed_unit_price,
            )
        )
        db.commit()


def test_list_allocations_endpoint_returns_financial_fields(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    End-to-end smoke test for the extended GET
    /{cycle_id}/allocations response - confirms the router/schema
    wiring, not just the service function in isolation.
    """

    products = {product.name: product for product in test_products}
    bed_frame = products["Test Bed Frame"]

    allocation = _create_allocation(
        db,
        optimization_cycle.id,
        bed_frame.id,
        Decimal("2.0000"),
    )

    try:
        response = client.get(
            f"/api/production-cycles/{optimization_cycle.id}/allocations"
        )

        assert response.status_code == 200

        data = response.json()
        row = next(
            item
            for item in data
            if item["product_id"] == bed_frame.id
        )

        assert Decimal(row["quantity"]) == Decimal("2.0000")
        assert "total_revenue" in row
        assert "total_cost" in row
        assert "total_profit" in row
        assert Decimal(row["total_revenue"]) == (
            bed_frame.selling_price * Decimal("2.0000")
        )

    finally:
        _delete_allocation(db, allocation)
