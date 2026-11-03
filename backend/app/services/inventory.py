from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Product, SalesTransaction
from app.services.opening_inventory import (
    get_opening_quantities,
    get_reviewed_opening_inventory_set,
    is_stock_validation_enabled,
)
from app.services.production import get_latest_production_cycle
from app.services.production_application import (
    get_cycle_produced_by_product,
    get_total_produced_by_product,
)


def lock_product_for_stock_update(
    db: Session,
    product_id: int,
) -> None:
    """
    Serialises stock-changing work for ONE product.

    Available stock is derived, not stored, so there is no row whose
    own constraint could reject an oversell - two concurrent sales
    would each read the same stock figure, each find room, and both
    commit. Locking the product row makes the read-check-write
    sequence atomic with respect to any other request touching the
    same product, which is the only thing that actually prevents it.

    Takes the lock on `products` rather than on the sales rows because
    the quantity being protected is a SUM over rows that do not exist
    yet - there is nothing in sales_transactions to lock. The lock is
    held until the caller's commit or rollback.

    Different products never block each other: two sales of different
    furniture items take different locks and proceed in parallel.
    """

    db.execute(
        select(Product.id)
        .where(Product.id == product_id)
        .with_for_update()
    ).scalar_one_or_none()


def get_total_sold_by_product(
    db: Session,
    since: datetime | None = None,
) -> dict[int, Decimal]:
    """
    product_id -> units sold across ALL time, every cycle included and
    rows with a NULL production_cycle_id included too. Deliberately
    never cycle-filtered: a sale reduced real stock whenever it
    happened, so excluding any sale here would overstate what is on
    hand.

    `since`, when given, excludes any sale recorded strictly before
    that instant - the ledger's effective date (see
    get_available_stock). A sale at or after `since` is still
    included in full. `None` (the default) keeps the true all-time
    total, so every other caller is unaffected.
    """

    statement = select(
        SalesTransaction.product_id,
        func.sum(SalesTransaction.quantity),
    )

    if since is not None:
        statement = statement.where(
            SalesTransaction.transaction_date >= since
        )

    rows = db.execute(
        statement.group_by(SalesTransaction.product_id)
    ).all()

    return {
        product_id: total
        for product_id, total in rows
        if total is not None
    }


def get_cycle_sold_by_product(
    db: Session,
    cycle_id: int,
) -> dict[int, Decimal]:
    """
    product_id -> units sold within ONE cycle. Resets for a new cycle
    (no rows yet) while get_total_sold_by_product keeps growing - the
    sold half of "cycle totals reset, stock carries over". Rows with a
    NULL production_cycle_id are excluded here by construction, which
    is correct: they belong to no cycle.
    """

    rows = db.execute(
        select(
            SalesTransaction.product_id,
            func.sum(SalesTransaction.quantity),
        )
        .where(SalesTransaction.production_cycle_id == cycle_id)
        .group_by(SalesTransaction.product_id)
    ).all()

    return {
        product_id: total
        for product_id, total in rows
        if total is not None
    }


def get_available_stock(db: Session) -> dict[int, Decimal]:
    """
    product_id -> units on hand right now:

        opening (reviewed declaration) + all production applied
        on or after the ledger's effective date
        - all sales recorded on or after the ledger's effective date

    The effective date is the currently REVIEWED OpeningInventorySet's
    own `effective_date` - reused rather than introducing a second
    "when does the ledger start" value. Sales and production recorded
    strictly BEFORE it never enter this calculation at all, in either
    direction: a historical sale from before the ledger existed does
    not deduct from it, and a historical production run from before it
    does not inflate it. With no REVIEWED set, `since` resolves to
    `None` and every call below falls back to its true all-time total
    - matching today's behavior exactly, since in that state
    is_stock_validation_enabled() already refuses every sale anyway.

    DERIVED on every read, never stored. A stored counter would have
    to be reversed correctly on every transaction edit and delete
    (both of which the API supports) and would drift the first time a
    reversal was missed; a sum cannot drift. Products absent from every
    source resolve to zero via the union below rather than being
    omitted, so a caller can always look up any product id.

    Floored at zero: stock can only go negative through pre-existing
    data (a legacy sale of stock the ledger never recorded), and
    reporting a negative on-hand figure would be a lie about physical
    goods. The sales-validation path in transaction.py is what keeps
    NEW sales from creating that state in the first place.
    """

    reviewed_set = get_reviewed_opening_inventory_set(db)
    since = (
        reviewed_set.effective_date
        if reviewed_set is not None
        else None
    )

    opening = get_opening_quantities(db)
    produced = get_total_produced_by_product(db, since=since)
    sold = get_total_sold_by_product(db, since=since)

    product_ids = (
        set(opening) | set(produced) | set(sold)
    )

    return {
        product_id: max(
            Decimal("0"),
            opening.get(product_id, Decimal("0"))
            + produced.get(product_id, Decimal("0"))
            - sold.get(product_id, Decimal("0")),
        )
        for product_id in product_ids
    }


def get_available_stock_for_product(
    db: Session,
    product_id: int,
) -> Decimal:
    """
    Single-product convenience over get_available_stock. A product
    with no opening balance, no production and no sales correctly
    resolves to zero rather than raising.
    """

    return get_available_stock(db).get(
        product_id,
        Decimal("0"),
    )


def get_unattributed_produced(
    db: Session,
    cycle_id: int,
    product_id: int,
) -> Decimal:
    """
    Newly applied production in this cycle that no transaction has
    recorded yet:

        cycle produced - sum of quantity_produced already recorded
        on this cycle's transactions for this product

    This is what a new transaction's quantity_produced is auto-filled
    with, and it is a DRAWDOWN, not a running total: the first sale
    after an apply carries the newly produced units, later sales in
    the same cycle carry zero. That guarantees the cycle's
    quantity_produced sum equals what the cycle actually produced, so
    the column can never overstate production however many
    transactions someone happens to record.

    (R1) Demand Forecasting no longer reads this column for new
    production - forecasting.py::get_production_event_series reads
    the ledger directly - so this invariant now protects the stored
    column, per-transaction production cost, and Transaction
    History, rather than the chart.

    Explicitly NOT available stock. Available stock spans every cycle
    and includes opening inventory; using it here would report units
    produced in earlier cycles as if they were produced now.

    Floored at zero so a legacy row whose hand-typed quantity_produced
    exceeds what the cycle produced yields 0 rather than a negative
    auto-fill.
    """

    produced = get_cycle_produced_by_product(db, cycle_id).get(
        product_id,
        Decimal("0"),
    )

    attributed = db.scalar(
        select(
            func.coalesce(
                func.sum(SalesTransaction.quantity_produced),
                0,
            )
        ).where(
            SalesTransaction.production_cycle_id == cycle_id,
            SalesTransaction.product_id == product_id,
        )
    ) or Decimal("0")

    return max(Decimal("0"), produced - attributed)


def get_inventory_overview(db: Session) -> dict:
    """
    Every figure a stock-aware screen needs, for every active product,
    keeping the three distinct quantities the spec calls out visibly
    separate: cycle produced, cycle sold, and all-cycles available
    stock.
    """

    cycle = get_latest_production_cycle(db)

    reviewed_set = get_reviewed_opening_inventory_set(db)
    since = (
        reviewed_set.effective_date
        if reviewed_set is not None
        else None
    )

    opening = get_opening_quantities(db)
    produced = get_total_produced_by_product(db, since=since)
    sold = get_total_sold_by_product(db, since=since)
    stock = get_available_stock(db)

    cycle_produced = (
        get_cycle_produced_by_product(db, cycle.id)
        if cycle is not None
        else {}
    )

    cycle_sold = (
        get_cycle_sold_by_product(db, cycle.id)
        if cycle is not None
        else {}
    )

    products = db.scalars(
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.id)
    ).all()

    return {
        "cycle_id": cycle.id if cycle is not None else None,
        "cycle_start_date": (
            cycle.start_date if cycle is not None else None
        ),
        "cycle_end_date": (
            cycle.end_date if cycle is not None else None
        ),
        "stock_validation_enabled": (
            is_stock_validation_enabled(db)
        ),
        "products": [
            {
                "product_id": product.id,
                "product_name": product.name,
                "opening_quantity": opening.get(
                    product.id, Decimal("0"),
                ),
                "total_produced": produced.get(
                    product.id, Decimal("0"),
                ),
                "total_sold": sold.get(
                    product.id, Decimal("0"),
                ),
                "available_stock": stock.get(
                    product.id, Decimal("0"),
                ),
                "cycle_produced": cycle_produced.get(
                    product.id, Decimal("0"),
                ),
                "cycle_sold": cycle_sold.get(
                    product.id, Decimal("0"),
                ),
            }
            for product in products
        ],
    }
