from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.database.models import Product, SalesTransaction
from app.schemas.transaction import (
    SalesTransactionCreate,
    SalesTransactionUpdate,
    TransactionRangeMode,
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

    values = calculate_transaction_values(
        transaction_data.quantity_produced,
        transaction_data.quantity,
        transaction_data.unit_price,
        transaction_data.production_cost,
    )

    transaction = SalesTransaction(
        transaction_number=generate_transaction_number(db),
        product_id=transaction_data.product_id,
        transaction_date=transaction_data.transaction_date,
        quantity_produced=transaction_data.quantity_produced,
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

    # transaction.production_cost is the stored TOTAL (see
    # calculate_transaction_values). If this request doesn't send a
    # new production_cost, reconstruct the per-unit rate that produced
    # the currently-stored total using the quantity_produced that was
    # in effect when it was last saved - not the raw stored total
    # itself, which would otherwise be multiplied again below and
    # silently inflate the cost.
    if "production_cost" in update_data:
        production_cost_per_unit = update_data["production_cost"]
    else:
        production_cost_per_unit = (
            transaction.production_cost
            / transaction.quantity_produced
        )

    values = calculate_transaction_values(
        quantity_produced,
        quantity,
        unit_price,
        production_cost_per_unit,
    )

    for field, value in update_data.items():
        setattr(transaction, field, value)

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