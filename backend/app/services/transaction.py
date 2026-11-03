from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Product,
    ProductionCycle,
    SalesTransaction,
)
from app.schemas.transaction import (
    SalesTransactionCreate,
    SalesTransactionUpdate,
    TransactionRangeMode,
)
from app.services.inventory import (
    get_available_stock_for_product,
    lock_product_for_stock_update,
)
from app.services.opening_inventory import (
    OpeningInventoryRequiredError,
    is_stock_validation_enabled,
)


# The default Transaction History view covers this many distinct
# transaction DATES - not this many calendar days counted back from
# today. The window is anchored to the newest row in the table and
# skips dates with no transactions entirely, so a shop that sold on
# Aug 23, Sep 5 and Oct 14 has three days of history, not fifty-two.
# Anchoring to the caller's clock instead would show an empty table
# for data only a few weeks old, and would make the default view
# depend on the browser's timezone; anchoring to the data does not.
DEFAULT_RECENT_TRANSACTION_DAYS = 7


def validate_transaction_date_range(
    start_date: date | None,
    end_date: date | None,
) -> None:
    if (
        start_date is not None
        and end_date is not None
        and end_date < start_date
    ):
        raise ValueError(
            "end_date must be greater than or equal to start_date"
        )


def resolve_production_cycle_for_date(
    db: Session,
    transaction_date: datetime,
) -> ProductionCycle | None:
    """
    The production cycle a sale belongs to, by date - or `None` if no
    cycle covers it. A Production Cycle is no longer a precondition
    for recording a sale: students may add transactions for any valid
    date, with or without a matching cycle. A sale is still attributed
    to a cycle whenever exactly one genuinely covers its date, so
    cycle-scoped reporting (cycle_sold, etc.) stays accurate whenever
    possible - it is only ever None when there is truly nothing to
    attribute it to.

    Membership is HALF-OPEN on the end bound:
    date(start_date) <= date(transaction_date) < date(end_date). That
    is the only rule under which seed.py's
    `end_date = start_date + timedelta(days=7)` describes exactly
    seven days AND back-to-back cycles never overlap - an inclusive
    end bound would make every boundary date belong to two cycles.

    Compared on the calendar DATE component only: transaction_date
    arrives from the UI as YYYY-MM-DDT00:00:00 while cycle bounds may
    carry a time, so a raw timestamp comparison would make cycle
    membership depend on the submitting browser's clock.

    Two matching cycles (possible only with hand-created overlapping
    cycles) are still rejected rather than resolved by a tiebreak -
    picking one would be a silent, wrong assignment, which is a real
    data-integrity problem independent of whether a cycle is required
    at all. Only the "zero matches" case changed from a rejection to a
    None result.
    """

    target_day = transaction_date.date()

    matches = list(
        db.scalars(
            select(ProductionCycle)
            .where(
                cast(ProductionCycle.start_date, Date)
                <= target_day,
                cast(ProductionCycle.end_date, Date) > target_day,
            )
            .order_by(ProductionCycle.id)
        ).all()
    )

    if not matches:
        return None

    if len(matches) > 1:
        names = ", ".join(
            f"#{cycle.id} "
            f"({cycle.start_date.date().isoformat()} to "
            f"{cycle.end_date.date().isoformat()})"
            for cycle in matches
        )

        raise ValueError(
            f"{target_day.isoformat()} falls within more than one "
            f"production cycle ({names}). Correct the overlapping "
            "cycle dates before recording this transaction."
        )

    return matches[0]


# transaction_date is a DateTime column (see
# app/database/models.py), so every date comparison here goes through
# the calendar DAY rather than the raw timestamp - two rows on the
# same date must count once toward the window regardless of the time
# of day they carry.
def _transaction_day():
    return cast(SalesTransaction.transaction_date, Date)


def get_available_transaction_dates(
    db: Session,
) -> tuple[date | None, date | None]:
    """
    The full span of transaction_date in the table, independent of
    any active window. Both values are None when the table is empty.
    """

    day = _transaction_day()

    earliest, latest = db.execute(
        select(func.min(day), func.max(day))
    ).one()

    return earliest, latest


def resolve_latest_available_window(
    db: Session,
    days: int = DEFAULT_RECENT_TRANSACTION_DAYS,
) -> tuple[date | None, date | None]:
    """
    Resolve the default window from the stored data: take the `days`
    most recent DISTINCT transaction dates and return their span.

    Expressed as a span rather than a set of dates because the two
    are equivalent here - a date inside the span with no rows
    contributes nothing either way - and a span composes with the
    same filter the custom-range mode uses.

    Fewer than `days` distinct dates needs no special case: min()
    simply returns the earliest date present, so the window widens to
    cover everything there is. An empty table yields (None, None).
    """

    day = _transaction_day()

    recent_days = (
        select(day.label("day"))
        .distinct()
        .order_by(day.desc())
        .limit(days)
        .subquery()
    )

    start_day, end_day = db.execute(
        select(
            func.min(recent_days.c.day),
            func.max(recent_days.c.day),
        )
    ).one()

    return start_day, end_day


def get_transactions(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[SalesTransaction]:
    statement = select(SalesTransaction)

    if start_date is not None:
        statement = statement.where(
            SalesTransaction.transaction_date
            >= datetime.combine(start_date, time.min)
        )

    if end_date is not None:
        # Half-open upper bound, deliberately not `<= end_date`:
        # end_date arrives as a calendar date, so comparing directly
        # would pin the bound to midnight and silently drop any row
        # stored with a nonzero time component on that same date.
        statement = statement.where(
            SalesTransaction.transaction_date
            < datetime.combine(
                end_date + timedelta(days=1),
                time.min,
            )
        )

    # Unchanged from before this endpoint gained any filtering:
    # (transaction_date, id), so rows sharing a date keep a stable
    # insertion-ordered sequence. Demand Forecasting relies on this
    # same ordering (app/services/forecasting.py).
    statement = statement.order_by(
        SalesTransaction.transaction_date,
        SalesTransaction.id,
    )

    return list(db.scalars(statement).all())


def get_transaction_list(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    show_all: bool = False,
) -> dict:
    """
    The three mutually exclusive modes behind GET /api/transactions,
    plus the metadata the client needs to describe what it is showing.

    Passing no parameters is NOT "give me everything" - it resolves
    the latest-available window. Callers that genuinely want the
    complete history must say so with show_all=True, so that intent
    is explicit at every call site rather than inferred from an
    absent parameter.
    """

    if show_all and (
        start_date is not None or end_date is not None
    ):
        raise ValueError(
            "show_all cannot be combined with start_date or end_date"
        )

    validate_transaction_date_range(start_date, end_date)

    earliest, latest = get_available_transaction_dates(db)

    available = (
        {"earliest": earliest, "latest": latest}
        if earliest is not None and latest is not None
        else None
    )

    if show_all:
        items = get_transactions(db)

        return {
            "items": items,
            "total": len(items),
            "range": None,
            "available": available,
        }

    if start_date is not None or end_date is not None:
        items = get_transactions(db, start_date, end_date)

        return {
            "items": items,
            "total": len(items),
            # Reported exactly as applied: a one-sided custom range
            # keeps its open bound null rather than being backfilled
            # from `available`, which would misreport the filter.
            "range": {
                "start_date": start_date,
                "end_date": end_date,
                "mode": TransactionRangeMode.CUSTOM,
            },
            "available": available,
        }

    window_start, window_end = resolve_latest_available_window(db)

    if window_start is None or window_end is None:
        # Empty table - there is no window to report, and `range`
        # stays null rather than inventing one around today.
        return {
            "items": [],
            "total": 0,
            "range": None,
            "available": available,
        }

    items = get_transactions(db, window_start, window_end)

    return {
        "items": items,
        "total": len(items),
        "range": {
            "start_date": window_start,
            "end_date": window_end,
            "mode": TransactionRangeMode.LATEST_AVAILABLE,
        },
        "available": available,
    }


def get_transaction(
    db: Session,
    transaction_id: int,
) -> SalesTransaction | None:
    statement = select(SalesTransaction).where(
        SalesTransaction.id == transaction_id
    )

    return db.scalars(statement).first()


def calculate_transaction_values(
    quantity_produced: Decimal,
    quantity: Decimal,
    unit_price: Decimal,
    production_cost_per_unit: Decimal,
) -> dict:
    # unit_price/production_cost_per_unit are both per-unit inputs.
    # Sales revenue is earned on units SOLD; production cost is
    # incurred on units PRODUCED - these are deliberately different
    # quantities (see the per-unit production cost requirement).
    # production_cost here is the computed TOTAL, mirroring total_sales
    # - the SalesTransaction.production_cost column already documents
    # itself as "Total production cost associated with this
    # transaction", so this was always its intended meaning; only the
    # multiplication by quantity_produced was previously missing.
    total_sales = (
        quantity * unit_price
    ).quantize(Decimal("0.01"))

    production_cost = (
        quantity_produced * production_cost_per_unit
    ).quantize(Decimal("0.01"))

    total_profit = (
        total_sales - production_cost
    ).quantize(Decimal("0.0000"))

    unit_profit = (
        (total_profit / quantity).quantize(Decimal("0.0000"))
        if quantity != 0
        else Decimal("0.0000")
    )

    return {
        "total_sales": total_sales,
        "production_cost": production_cost,
        "unit_profit": unit_profit,
        "total_profit": total_profit,
    }

def generate_transaction_number(db: Session) -> str:
    last_id = db.scalar(
        select(func.max(SalesTransaction.id))
    )

    next_id = (last_id or 0) + 1

    return f"TRX-{next_id:06d}"

def create_transaction(
    db: Session,
    transaction_data: SalesTransactionCreate,
) -> SalesTransaction:
    # Checked FIRST, before any other validation (Ruling 28): the gate
    # is a precondition on the OPERATION, not on the payload, so the
    # answer is the same regardless of what was submitted.
    #
    # AMENDMENT A: this REFUSES the sale rather than skipping
    # validation. The plan's original Task 10 body wrapped the stock
    # check in `if is_stock_validation_enabled(db):` and recorded sales
    # unvalidated until an opening balance was reviewed - that is the
    # rejected soft gate, because it left a window in which true stock
    # could go negative and the derived figure's zero-floor would then
    # hide the deficit instead of preventing it.
    if not is_stock_validation_enabled(db):
        raise OpeningInventoryRequiredError(
            "Opening inventory must be declared and reviewed "
            "before sales can be recorded. Every active product "
            "that existed on the effective date needs an explicit "
            "opening quantity, including zero."
        )

    product = db.get(
        Product,
        transaction_data.product_id,
    )

    if product is None:
        raise ValueError("Product not found")

    if not product.is_active:
        raise ValueError(
            "Cannot create transaction for inactive product"
        )

    # A Production Cycle is no longer required to record a sale -
    # None is a normal, accepted result here. Still rejects a date
    # covered by more than one cycle instead of attributing the sale
    # to either - a sale in the wrong cycle would silently corrupt
    # that cycle's reported sales.
    production_cycle = resolve_production_cycle_for_date(
        db,
        transaction_data.transaction_date,
    )

    # Serialises every stock-changing request for THIS product.
    # Available stock is a derived SUM, so there is no row constraint
    # that could reject an oversell: without this lock two concurrent
    # sales both read the same figure, both find room, and both
    # commit. Taken BEFORE the stock figure is read, and held until
    # this function's commit or rollback.
    lock_product_for_stock_update(db, product.id)

    # Unconditional - see the gate above. Once a complete reviewed
    # opening balance exists, every sale is validated against stock;
    # there is no bypass.
    available_stock = get_available_stock_for_product(
        db,
        product.id,
    )

    if transaction_data.quantity > available_stock:
        raise ValueError(
            f"Cannot sell {transaction_data.quantity} units of "
            f"{product.name} - only {available_stock} units are "
            "available. Apply a production plan to produce more, "
            "or reduce the quantity sold."
        )

    # Server-computed, ignoring any client-sent value - and now the
    # SAME all-time available balance the Add Transaction modal
    # already displays (opening + production applied in ANY cycle -
    # sales across all time), not a per-cycle drawdown. A cycle-local
    # drawdown undercounts the moment a sale's own cycle differs from
    # the cycle production was actually applied to (e.g. production
    # applied under an old cycle, a sale recorded once a new cycle
    # covers today's date) - exactly the mismatch that produced a
    # saved 0 despite 5 units being genuinely available. Computed
    # BEFORE this sale's own row exists, so it is pre-sale stock, the
    # same value `available_stock` above was just validated against -
    # reused directly rather than recomputed. (R1: the forecast chart
    # reads production from the ledger, not from this column, so
    # widening what this column means does not affect it.)
    quantity_produced = available_stock

    values = calculate_transaction_values(
        quantity_produced,
        transaction_data.quantity,
        transaction_data.unit_price,
        transaction_data.production_cost,
    )

    transaction = SalesTransaction(
        transaction_number=generate_transaction_number(db),
        product_id=transaction_data.product_id,
        production_cycle_id=(
            production_cycle.id
            if production_cycle is not None
            else None
        ),
        transaction_date=transaction_data.transaction_date,
        quantity_produced=quantity_produced,
        quantity=transaction_data.quantity,
        unit_price=transaction_data.unit_price,
        total_sales=values["total_sales"],
        production_cost=values["production_cost"],
        unit_profit=values["unit_profit"],
        total_profit=values["total_profit"],
    )

    try:
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise


def update_transaction(
    db: Session,
    transaction: SalesTransaction,
    transaction_data: SalesTransactionUpdate,
) -> SalesTransaction:
    """
    quantity_produced is deliberately NOT recomputed on update. It
    records what was newly produced at the moment the transaction was
    first recorded; re-deriving it now would reshuffle the drawdown
    across every row in the cycle and rewrite settled history. A
    client-sent quantity_produced is still accepted (the field remains
    on SalesTransactionUpdate) so a genuine correction stays possible,
    but it is not auto-filled.
    """

    update_data = transaction_data.model_dump(
        exclude_unset=True
    )

    quantity_produced = update_data.get(
        "quantity_produced",
        transaction.quantity_produced,
    )

    quantity = update_data.get(
        "quantity",
        transaction.quantity,
    )

    unit_price = update_data.get(
        "unit_price",
        transaction.unit_price,
    )

    transaction_date = update_data.get(
        "transaction_date",
        transaction.transaction_date,
    )

    # Re-resolve the cycle whenever the date moves, so a sale is never
    # left attributed to its OLD cycle once the date no longer belongs
    # to it. A Production Cycle is not required, so "no cycle covers
    # the new date" is now a normal None result, not a rejection.
    #
    # (R1) A row with no cycle today (whether a genuine pre-rollout
    # legacy row, or a newer sale recorded with no matching cycle) is
    # exempt from re-resolution: production_cycle_id IS NULL still
    # marks a row the forecast's legacy fallback may read (gated by
    # transaction_date against the ledger's effective date - see
    # forecasting.py), and an unrelated date edit must never silently
    # attribute such a row to a cycle it was never actually produced
    # under. It stays unattributed, exactly as it was before this
    # edit.
    production_cycle_id = transaction.production_cycle_id

    if (
        "transaction_date" in update_data
        and transaction.production_cycle_id is not None
    ):
        resolved_cycle = resolve_production_cycle_for_date(
            db,
            transaction_date,
        )

        production_cycle_id = (
            resolved_cycle.id
            if resolved_cycle is not None
            else None
        )

    # Same lock, same reason, as create_transaction: the stock figure
    # about to be checked is a derived SUM with no row constraint
    # behind it.
    lock_product_for_stock_update(db, transaction.product_id)

    # AMENDMENT A (closes R-23b): the plan's original body wrapped
    # everything below in `if is_stock_validation_enabled(db):`, which
    # would let an edit raise a sale above available stock while no
    # opening balance had been reviewed - the same soft gate rejected
    # for create. An edit is a stock-affecting operation, so it is
    # refused rather than waved through.
    #
    # DELETE is deliberately NOT gated: removing a sale only RETURNS
    # stock, so it can never drive the figure negative, and blocking
    # corrections would cost something while protecting nothing.
    if not is_stock_validation_enabled(db):
        raise OpeningInventoryRequiredError(
            "Opening inventory must be declared and reviewed "
            "before sales can be edited. Every active product "
            "that existed on the effective date needs an explicit "
            "opening quantity, including zero."
        )

    product = db.get(Product, transaction.product_id)

    # This row's CURRENT quantity is already deducted from available
    # stock, so it has to be added back before the proposed quantity
    # is weighed - otherwise raising 4 to 10 against 10 produced units
    # reads as a demand for 14 and is wrongly rejected (the same
    # self-double-counting trap
    # allocation.py::_validate_proposed_allocation_capacity documents).
    available_stock = (
        get_available_stock_for_product(
            db,
            transaction.product_id,
        )
        + transaction.quantity
    )

    if quantity > available_stock:
        raise ValueError(
            f"Cannot sell {quantity} units of "
            f"{product.name if product else 'this product'} - "
            f"only {available_stock} units are available. Apply a "
            "production plan to produce more, or reduce the "
            "quantity sold."
        )

    # transaction.production_cost is the stored TOTAL (see
    # calculate_transaction_values). If this request doesn't send a
    # new production_cost, reconstruct the per-unit rate that produced
    # the currently-stored total using the quantity_produced that was
    # in effect when it was last saved - not the raw stored total
    # itself, which would otherwise be multiplied again below and
    # silently inflate the cost.
    #
    # quantity_produced == 0 is a NORMAL stored value since produced
    # quantities became a per-cycle drawdown (the second sale in a
    # cycle records 0), so the division has to be guarded: a zero
    # produced quantity means zero total cost, and any per-unit rate
    # reproduces that.
    if "production_cost" in update_data:
        production_cost_per_unit = update_data["production_cost"]
    elif transaction.quantity_produced:
        production_cost_per_unit = (
            transaction.production_cost
            / transaction.quantity_produced
        )
    else:
        production_cost_per_unit = Decimal("0")

    values = calculate_transaction_values(
        quantity_produced,
        quantity,
        unit_price,
        production_cost_per_unit,
    )

    for field, value in update_data.items():
        setattr(transaction, field, value)

    transaction.production_cycle_id = production_cycle_id
    transaction.total_sales = values["total_sales"]
    transaction.production_cost = values["production_cost"]
    transaction.unit_profit = values["unit_profit"]
    transaction.total_profit = values["total_profit"]

    try:
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise


def delete_transaction(
    db: Session,
    transaction: SalesTransaction,
) -> None:
    try:
        db.delete(transaction)
        db.commit()

    except Exception:
        db.rollback()
        raise