from datetime import datetime
from decimal import Decimal

from app.database.models import OpeningInventoryItem, OpeningInventorySet


def _review_opening(db, product_id, quantity):
    inventory_set = OpeningInventorySet(
        set_number=f"OI-INV{product_id}",
        status="REVIEWED",
        effective_date=datetime(2026, 10, 1),
        reviewed_at=datetime(2026, 10, 1),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product_id,
            quantity=Decimal(str(quantity)),
        )
    )

    db.commit()

    return inventory_set


def test_available_stock_is_opening_plus_produced_minus_sold(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    The one formula the whole feature rests on. Opening inventory is a
    real starting balance - not zero - so it must appear in the sum.
    """

    from app.services.inventory import get_available_stock_for_product
    from app.services.production_application import (
        save_production_application,
    )
    from app.database.models import OptimizationRun, SalesTransaction

    product = test_products[0]

    _review_opening(db, product.id, 4)

    run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {product.id: Decimal("10")},
        [],
    )
    db.commit()

    sale = SalesTransaction(
        transaction_number="TRX-INV0001",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity_produced=Decimal("10"),
        quantity=Decimal("5"),
        unit_price=Decimal("100"),
        total_sales=Decimal("500"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("500"),
    )

    db.add(sale)
    db.commit()

    try:
        # 4 opening + 10 produced - 5 sold
        assert get_available_stock_for_product(
            db, product.id,
        ) == Decimal("9")

    finally:
        db.delete(sale)
        db.commit()


def test_stock_is_zero_based_on_opening_when_nothing_else_exists(
    db, cleanup_opening_inventory, cleanup_applications, test_products,
):
    """
    Opening inventory alone IS available stock before any production
    or sales - the explicit rejection of "start at zero".
    """

    from app.services.inventory import get_available_stock_for_product

    product = test_products[0]

    _review_opening(db, product.id, 7)

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("7")


def test_unreviewed_opening_inventory_does_not_count(
    db, cleanup_opening_inventory, cleanup_applications, test_products,
):
    from app.services.inventory import get_available_stock_for_product

    product = test_products[0]

    inventory_set = OpeningInventorySet(
        set_number="OI-INVDRAFT",
        status="DRAFT",
        effective_date=datetime(2026, 10, 1),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=product.id,
            quantity=Decimal("99"),
        )
    )

    db.commit()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("0")


def test_cycle_totals_reset_while_stock_carries_over(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    Requirement 5, exactly: a new cycle starts its produced and sold
    totals at zero while actual available inventory is untouched.
    """

    from app.database.models import (
        OptimizationRun,
        ProductionCycle,
        SalesTransaction,
    )
    from app.services.inventory import (
        get_available_stock_for_product,
        get_cycle_sold_by_product,
    )
    from app.services.production_application import (
        get_cycle_produced_by_product,
        save_production_application,
    )

    product = test_products[0]

    run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {product.id: Decimal("10")},
        [],
    )
    db.commit()

    sale = SalesTransaction(
        transaction_number="TRX-INV0002",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity_produced=Decimal("10"),
        quantity=Decimal("4"),
        unit_price=Decimal("100"),
        total_sales=Decimal("400"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("400"),
    )

    db.add(sale)
    db.commit()

    next_cycle = ProductionCycle(
        cycle_date=datetime(2026, 12, 20),
        start_date=datetime(2026, 12, 20),
        end_date=datetime(2026, 12, 27),
        status="OPEN",
    )

    db.add(next_cycle)
    db.commit()
    db.refresh(next_cycle)

    try:
        # Cycle-scoped figures for the NEW cycle are empty...
        assert get_cycle_produced_by_product(
            db, next_cycle.id,
        ).get(product.id, Decimal("0")) == Decimal("0")

        assert get_cycle_sold_by_product(
            db, next_cycle.id,
        ).get(product.id, Decimal("0")) == Decimal("0")

        # ...while the unsold units survive the boundary.
        assert get_available_stock_for_product(
            db, product.id,
        ) == Decimal("6")

    finally:
        db.delete(sale)
        db.delete(next_cycle)
        db.commit()


def test_unattributed_produced_draws_down_within_a_cycle(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    The rule that keeps the forecast chart honest: the first sale after
    an apply carries the newly produced units, a later sale in the same
    cycle carries zero, so the cycle's quantity_produced sum can never
    exceed what the cycle actually produced.
    """

    from app.database.models import OptimizationRun, SalesTransaction
    from app.services.inventory import get_unattributed_produced
    from app.services.production_application import (
        save_production_application,
    )

    product = test_products[0]

    run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    save_production_application(
        db,
        optimization_cycle.id,
        run.id,
        {product.id: Decimal("10")},
        [],
    )
    db.commit()

    assert get_unattributed_produced(
        db, optimization_cycle.id, product.id,
    ) == Decimal("10")

    sale = SalesTransaction(
        transaction_number="TRX-INV0003",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity_produced=Decimal("10"),
        quantity=Decimal("3"),
        unit_price=Decimal("100"),
        total_sales=Decimal("300"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("300"),
    )

    db.add(sale)
    db.commit()

    try:
        assert get_unattributed_produced(
            db, optimization_cycle.id, product.id,
        ) == Decimal("0")

    finally:
        db.delete(sale)
        db.commit()


def test_unattributed_produced_never_goes_negative(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    A legacy row with a hand-typed quantity_produced larger than the
    cycle ever produced must floor at zero, not hand back a negative
    auto-fill value.
    """

    from app.database.models import SalesTransaction
    from app.services.inventory import get_unattributed_produced

    product = test_products[0]

    sale = SalesTransaction(
        transaction_number="TRX-INV0004",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=datetime(2026, 10, 31),
        quantity_produced=Decimal("500"),
        quantity=Decimal("1"),
        unit_price=Decimal("100"),
        total_sales=Decimal("100"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("100"),
    )

    db.add(sale)
    db.commit()

    try:
        assert get_unattributed_produced(
            db, optimization_cycle.id, product.id,
        ) == Decimal("0")

    finally:
        db.delete(sale)
        db.commit()


def test_inventory_endpoint_reports_all_three_figures(
    client, db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    product = test_products[0]

    _review_opening(db, product.id, 2)

    response = client.get("/api/inventory")

    assert response.status_code == 200

    payload = response.json()

    assert payload["stock_validation_enabled"] is True
    assert payload["cycle_id"] is not None

    row = next(
        item for item in payload["products"]
        if item["product_id"] == product.id
    )

    for field in (
        "opening_quantity",
        "total_produced",
        "total_sold",
        "available_stock",
        "cycle_produced",
        "cycle_sold",
    ):
        assert field in row

    assert Decimal(row["opening_quantity"]) == Decimal("2")
    assert Decimal(row["available_stock"]) == Decimal("2")


def test_inventory_requires_authentication(unauthenticated_client):
    assert unauthenticated_client.get(
        "/api/inventory"
    ).status_code == 401
