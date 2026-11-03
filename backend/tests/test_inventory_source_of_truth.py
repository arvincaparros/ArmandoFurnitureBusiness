from decimal import Decimal
from pathlib import Path

from app.database.models import (
    ProductionApplication,
    ProductionApplicationItem,
)
from app.schemas.allocation import (
    ProductionAllocationCreate,
    ProductionAllocationUpdate,
)
from app.services.allocation import (
    create_allocation,
    delete_allocation,
    update_allocation,
)
from app.services.inventory import get_available_stock_for_product


def _ledger_counts(db):
    return (
        db.query(ProductionApplication).count(),
        db.query(ProductionApplicationItem).count(),
    )


def test_manual_allocation_crud_creates_no_inventory(
    db, cleanup_applications, optimization_cycle, test_products,
    test_product_resource_requirements,
):
    """
    ProductionAllocation is a PLAN. Only a successful apply records
    finished-goods production, so planning by hand must leave both the
    ledger and available stock untouched - create, update and delete.

    Uses optimization_cycle, not the plan's transaction_cycle: manual
    allocation CRUD validates against the cycle's CycleResource
    capacity, and transaction_cycle creates a bare ProductionCycle
    with no resources - so every create_allocation call was refused
    for 0 available capacity before reaching the behaviour under test.
    optimization_cycle is the fixture that priced and stocked the
    cycle's resources. The quantities below are unchanged and fit
    inside it.
    """

    product = test_products[0]

    before_counts = _ledger_counts(db)
    before_stock = get_available_stock_for_product(db, product.id)

    allocation = create_allocation(
        db,
        optimization_cycle.id,
        ProductionAllocationCreate(
            product_id=product.id,
            quantity=Decimal("5"),
        ),
    )

    assert _ledger_counts(db) == before_counts
    assert get_available_stock_for_product(
        db, product.id,
    ) == before_stock

    update_allocation(
        db,
        allocation,
        ProductionAllocationUpdate(quantity=Decimal("9")),
    )

    assert _ledger_counts(db) == before_counts
    assert get_available_stock_for_product(
        db, product.id,
    ) == before_stock

    delete_allocation(db, allocation)

    assert _ledger_counts(db) == before_counts
    assert get_available_stock_for_product(
        db, product.id,
    ) == before_stock


def test_apply_optimization_is_the_only_ledger_writer():
    """
    Grep-as-a-test: save_production_application must stay called from
    exactly one place. If this fails a new write path appeared, and the
    "only a successful apply records production" guarantee needs
    re-checking - not this assertion relaxing.

    production_application.py is listed because it holds the
    definition itself. Run from backend/, where the rest of the suite
    runs from.
    """

    services = Path("app/services")

    callers = sorted(
        path.name
        for path in services.glob("*.py")
        if "save_production_application(" in path.read_text(
            encoding="utf-8",
        )
    )

    assert callers == [
        "optimization.py",
        "production_application.py",
    ]
