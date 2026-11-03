from datetime import datetime
from decimal import Decimal

from app.database.models import OpeningInventoryItem, OpeningInventorySet


def _review_opening(
    db, product_id, quantity, effective_date=datetime(2026, 10, 1),
):
    inventory_set = OpeningInventorySet(
        set_number=f"OI-INV{product_id}",
        status="REVIEWED",
        effective_date=effective_date,
        reviewed_at=effective_date,
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
        "latest_applied_quantity",
    ):
        assert field in row

    assert Decimal(row["opening_quantity"]) == Decimal("2")
    assert Decimal(row["available_stock"]) == Decimal("2")


def test_inventory_requires_authentication(unauthenticated_client):
    assert unauthenticated_client.get(
        "/api/inventory"
    ).status_code == 401


def test_available_stock_excludes_sales_before_ledger_effective_date(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    Thesis-scope simplification: a sale recorded before the ledger's
    effective date must not deduct from the newly tracked inventory,
    even though get_total_sold_by_product's default (no `since`) is
    still all-time for every other caller.
    """

    from app.database.models import SalesTransaction
    from app.services.inventory import get_available_stock_for_product

    product = test_products[0]

    effective_date = datetime(2026, 11, 3)
    _review_opening(
        db, product.id, 10, effective_date=effective_date,
    )

    pre_ledger_sale = SalesTransaction(
        transaction_number="TRX-INV0005",
        product_id=product.id,
        production_cycle_id=None,
        transaction_date=datetime(2026, 9, 1),
        quantity_produced=Decimal("0"),
        quantity=Decimal("6"),
        unit_price=Decimal("100"),
        total_sales=Decimal("600"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("600"),
    )

    db.add(pre_ledger_sale)
    db.commit()

    try:
        assert get_available_stock_for_product(
            db, product.id,
        ) == Decimal("10")

    finally:
        db.delete(pre_ledger_sale)
        db.commit()


def test_available_stock_deducts_a_sale_exactly_at_the_effective_date(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    Boundary case called out explicitly: a transaction occurring at
    the SAME instant as the ledger's effective date (same calendar
    date as an apply event like PA-0001) must still be deducted - the
    cutoff is inclusive (>=), not exclusive.
    """

    from app.database.models import SalesTransaction
    from app.services.inventory import get_available_stock_for_product

    product = test_products[0]

    effective_date = datetime(2026, 11, 3)
    _review_opening(
        db, product.id, 10, effective_date=effective_date,
    )

    boundary_sale = SalesTransaction(
        transaction_number="TRX-INV0006",
        product_id=product.id,
        production_cycle_id=optimization_cycle.id,
        transaction_date=effective_date,
        quantity_produced=Decimal("0"),
        quantity=Decimal("4"),
        unit_price=Decimal("100"),
        total_sales=Decimal("400"),
        production_cost=Decimal("0"),
        unit_profit=Decimal("100"),
        total_profit=Decimal("400"),
    )

    db.add(boundary_sale)
    db.commit()

    try:
        assert get_available_stock_for_product(
            db, product.id,
        ) == Decimal("6")

    finally:
        db.delete(boundary_sale)
        db.commit()


def test_available_stock_excludes_production_before_ledger_effective_date(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    Mirrors the sales-side exclusion: a production application applied
    before the ledger's effective date must not inflate stock either -
    pre-ledger activity is excluded in both directions.
    """

    from app.database.models import (
        OptimizationRun,
        ProductionApplication,
        ProductionApplicationItem,
    )
    from app.services.inventory import get_available_stock_for_product

    product = test_products[0]

    effective_date = datetime(2026, 11, 3)
    _review_opening(
        db, product.id, 0, effective_date=effective_date,
    )

    pre_ledger_run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 9, 1, 9, 0),
        status="OPTIMAL",
    )

    db.add(pre_ledger_run)
    db.commit()
    db.refresh(pre_ledger_run)

    pre_ledger_application = ProductionApplication(
        application_number="PA-TESTPRE",
        production_cycle_id=optimization_cycle.id,
        optimization_run_id=pre_ledger_run.id,
        applied_at=datetime(2026, 9, 1),
    )

    db.add(pre_ledger_application)
    db.flush()

    db.add(
        ProductionApplicationItem(
            production_application_id=pre_ledger_application.id,
            product_id=product.id,
            quantity_produced=Decimal("20"),
        )
    )

    db.commit()

    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("0")


def test_available_stock_accumulates_multiple_applications_on_or_after_effective_date(
    db, cleanup_opening_inventory, cleanup_applications,
    optimization_cycle, test_products,
):
    """
    Requirement 3, under the new scoping: two separate applications
    both on or after the effective date must still both count, exactly
    as the unscoped formula already guaranteed. Scoping must not
    collapse accumulation.
    """

    from app.database.models import OptimizationRun
    from app.services.inventory import get_available_stock_for_product
    from app.services.production_application import (
        save_production_application,
    )

    product = test_products[0]

    # Deliberately far in the past relative to wall-clock "now" (not
    # tied to the day this suite happens to run) - the two
    # applications below get their real applied_at timestamp from
    # save_production_application's own datetime.utcnow() call, which
    # only needs to land on or after this effective_date, not on any
    # particular day.
    effective_date = datetime(2026, 1, 1)
    _review_opening(
        db, product.id, 0, effective_date=effective_date,
    )

    first_run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )
    db.add(first_run)
    db.commit()
    db.refresh(first_run)

    save_production_application(
        db, optimization_cycle.id, first_run.id,
        {product.id: Decimal("9")}, [],
    )
    db.commit()

    second_run = OptimizationRun(
        production_cycle_id=optimization_cycle.id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )
    db.add(second_run)
    db.commit()
    db.refresh(second_run)

    save_production_application(
        db, optimization_cycle.id, second_run.id,
        {product.id: Decimal("5")}, [],
    )
    db.commit()

    # save_production_application stamps applied_at via
    # datetime.utcnow() internally - both applications land well
    # after effective_date, so both must be counted.
    assert get_available_stock_for_product(
        db, product.id,
    ) == Decimal("14")


def test_latest_applied_quantity_reflects_only_the_most_recent_apply(
    client, db, cleanup_applications, optimization_cycle, test_products,
):
    """
    latest_applied_quantity must track only the SINGLE most recent
    Apply for a product (ProductionAllocation.quantity - wholesale-
    replaced on every Apply), never the cumulative within-cycle total
    cycle_produced reports. This is what Add Transaction's "Quantity
    Produced" field reads: a second Apply of the same batch size must
    still display that one batch, not a running sum.
    """

    from app.database.models import CycleResource

    chair = next(
        product for product in test_products
        if product.name == "Test Chair"
    )

    def _chair_row():
        payload = client.get("/api/inventory").json()

        return next(
            item for item in payload["products"]
            if item["product_id"] == chair.id
        )

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    ).status_code == 200

    first_row = _chair_row()

    assert Decimal(
        first_row["latest_applied_quantity"]
    ) == Decimal("12.0000")
    assert Decimal(first_row["cycle_produced"]) == Decimal(
        "12.0000"
    )

    # Restored Generate-independence workflow: generate the second
    # batch BEFORE topping up capacity (see the ordering note in
    # test_production_apply_ledger.py), then top up so the second
    # Apply has fresh material to consume.
    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    ).status_code == 200

    for cycle_resource in db.query(CycleResource).filter(
        CycleResource.production_cycle_id == optimization_cycle.id
    ).all():
        cycle_resource.available_quantity = (
            cycle_resource.available_quantity * Decimal("3")
        )

    db.commit()

    assert client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize/apply",
    ).status_code == 200

    second_row = _chair_row()

    # The same batch size again (12) - never the running sum (24).
    assert Decimal(
        second_row["latest_applied_quantity"]
    ) == Decimal("12.0000")
    assert Decimal(second_row["cycle_produced"]) == Decimal(
        "24.0000"
    )
