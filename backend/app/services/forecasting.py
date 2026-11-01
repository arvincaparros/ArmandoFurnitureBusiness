from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.forecast_history import save_forecast_history

from app.database.models import (
    Product,
    ProductionApplication,
    ProductionApplicationItem,
    SalesTransaction,
)


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1

    return year, month + 1


def get_monthly_historical_demand(
    db: Session,
) -> dict[int, list[dict]]:
    """
    Aggregate qualifying sales transactions into a chronological,
    zero-filled monthly demand series per active product.

    This is the shared historical data layer for the forecast
    algorithm and the forecast time-series endpoint - both should
    consume this instead of re-deriving monthly totals themselves.

    Returns, per product_id, a list of
    {"period": "YYYY-MM", "quantity": Decimal} covering every
    calendar month from that product's first to last qualifying
    transaction month, in ascending order, with months that have
    no qualifying transactions filled in as zero.
    """

    statement = (
        select(
            SalesTransaction.product_id,
            SalesTransaction.transaction_date,
            SalesTransaction.quantity,
        )
        .join(
            Product,
            Product.id == SalesTransaction.product_id,
        )
        .where(
            Product.is_active.is_(True),
            SalesTransaction.quantity > 0,
        )
        .order_by(
            SalesTransaction.product_id,
            SalesTransaction.transaction_date,
        )
    )

    rows = db.execute(statement).all()

    monthly_totals: dict[int, dict[tuple[int, int], Decimal]] = (
        defaultdict(dict)
    )

    for row in rows:
        month_key = (
            row.transaction_date.year,
            row.transaction_date.month,
        )

        product_totals = monthly_totals[row.product_id]

        product_totals[month_key] = (
            product_totals.get(month_key, Decimal("0"))
            + row.quantity
        )

    monthly_series: dict[int, list[dict]] = {}

    for product_id, totals in monthly_totals.items():
        months = sorted(totals.keys())

        year, month = months[0]
        last_year, last_month = months[-1]

        series = []

        while (year, month) <= (last_year, last_month):
            series.append(
                {
                    "period": f"{year:04d}-{month:02d}",
                    "quantity": totals.get(
                        (year, month),
                        Decimal("0"),
                    ),
                }
            )

            year, month = _next_month(year, month)

        monthly_series[product_id] = series

    return monthly_series


def get_transaction_historical_demand(
    db: Session,
) -> dict[int, list[dict]]:
    """
    Return the qualifying sales transactions per active product at
    full transaction granularity, in chronological order.

    This is the chart's historical data layer - one graph point
    per recorded transaction - and deliberately NOT the forecast
    algorithm's input: calculate_forecast() keeps consuming
    get_monthly_historical_demand()'s monthly totals, so the
    forecast keeps its monthly meaning and scale.

    Qualification matches the monthly layer exactly (active
    product, quantity > 0) so a transaction can never appear in
    one series and be missing from the other.

    Returns, per product_id, a list of
    {"period": "YYYY-MM-DD", "transaction_id": int,
     "transaction_number": str, "quantity": Decimal,
     "quantity_produced": Decimal | None} ordered by
    (transaction_date, id), so transactions sharing a date stay
    separate and keep a stable identity.

    "quantity_produced" is reported ONLY for pre-rollout rows -
    the ones with production_cycle_id IS NULL, written before the
    production application ledger existed. Their stored figure is
    the only production record they have, so the chart must keep
    rendering it exactly as it always did. Every cycle-attributed
    row reports None: its production is in the ledger, and
    get_production_event_series() is the authoritative source for
    it. Reporting both would plot the same units twice.
    """

    statement = (
        select(
            SalesTransaction.id,
            SalesTransaction.transaction_number,
            SalesTransaction.product_id,
            SalesTransaction.transaction_date,
            SalesTransaction.quantity,
            SalesTransaction.quantity_produced,
            SalesTransaction.production_cycle_id,
        )
        .join(
            Product,
            Product.id == SalesTransaction.product_id,
        )
        .where(
            Product.is_active.is_(True),
            SalesTransaction.quantity > 0,
        )
        .order_by(
            SalesTransaction.product_id,
            SalesTransaction.transaction_date,
            SalesTransaction.id,
        )
    )

    transactions: dict[int, list[dict]] = defaultdict(list)

    for row in db.execute(statement).all():
        transactions[row.product_id].append(
            {
                "period": row.transaction_date.strftime(
                    "%Y-%m-%d"
                ),
                "transaction_id": row.id,
                "transaction_number": row.transaction_number,
                "quantity": row.quantity,
                "quantity_produced": (
                    row.quantity_produced
                    if row.production_cycle_id is None
                    else None
                ),
            }
        )

    return dict(transactions)


def get_production_event_series(
    db: Session,
) -> dict[int, list[dict]]:
    """
    Return every applied production event per active product, one
    point per (production application, product), chronologically.

    This is the production counterpart of
    get_transaction_historical_demand(): the chart's production data
    layer. production_application_items is the authoritative source
    for new production - never ProductionAllocation (a plan, replaced
    wholesale on every apply), never SalesTransaction.quantity_produced
    (a cost attribution that only exists once something is sold), and
    never opening_inventory_items (a starting balance that was never
    produced here).

    Because every application row is its own event, production appears
    exactly once, on the date it was applied: ten sales cannot
    duplicate it, zero sales cannot hide it, and a previous cycle's
    application keeps its own date instead of being counted again in
    the current cycle.

    Qualification mirrors the sales layer (active product, positive
    quantity) so a product can never appear in one series and be
    missing from the other.

    Returns, per product_id, a list of
    {"period": "YYYY-MM-DD", "application_id": int,
     "application_number": str, "production_cycle_id": int,
     "quantity_produced": Decimal} ordered by
    (applied_at, application_id).
    """

    statement = (
        select(
            ProductionApplicationItem.product_id,
            ProductionApplicationItem.quantity_produced,
            ProductionApplication.id.label("application_id"),
            ProductionApplication.application_number,
            ProductionApplication.production_cycle_id,
            ProductionApplication.applied_at,
        )
        .join(
            ProductionApplication,
            ProductionApplication.id
            == ProductionApplicationItem.production_application_id,
        )
        .join(
            Product,
            Product.id == ProductionApplicationItem.product_id,
        )
        .where(
            Product.is_active.is_(True),
            ProductionApplicationItem.quantity_produced > 0,
        )
        .order_by(
            ProductionApplicationItem.product_id,
            ProductionApplication.applied_at,
            ProductionApplication.id,
        )
    )

    events: dict[int, list[dict]] = defaultdict(list)

    for row in db.execute(statement).all():
        events[row.product_id].append(
            {
                "period": row.applied_at.strftime("%Y-%m-%d"),
                "application_id": row.application_id,
                "application_number": row.application_number,
                "production_cycle_id": row.production_cycle_id,
                "quantity_produced": row.quantity_produced,
            }
        )

    return dict(events)


def calculate_data_score(months: int) -> Decimal:
    """
    Data-volume component of confidence_level: rewards more
    months of history, saturating at 6 months.
    """

    return Decimal(min(months, 6)) / Decimal(6) * Decimal(100)


def calculate_consistency_score(
    quantities: list[Decimal],
) -> Decimal:
    """
    Consistency component of confidence_level: rewards low
    relative variability (coefficient of variation) across the
    monthly series. Undefined with fewer than 2 points, and
    undefined when the mean is 0 - both are treated as 0
    (not yet assessable), never as neutral or positive.
    """

    months = len(quantities)

    if months < 2:
        return Decimal("0")

    mean = sum(quantities) / Decimal(months)

    if mean == 0:
        return Decimal("0")

    variance = sum(
        (quantity - mean) ** 2 for quantity in quantities
    ) / Decimal(months)

    coefficient_of_variation = variance.sqrt() / mean

    return max(
        Decimal("0"),
        Decimal("100") - coefficient_of_variation * Decimal("100"),
    )


def calculate_confidence_level(
    quantities: list[Decimal],
) -> Decimal:
    """
    Deterministic data-quality score in [0.00, 100.00], combining
    data volume and historical consistency in equal weight.

    This is NOT a machine-learned or statistical probability - it
    is a composite score derived purely from the shape of the
    observed monthly history.
    """

    months = len(quantities)

    data_score = calculate_data_score(months)
    consistency_score = calculate_consistency_score(quantities)

    confidence_level = (
        Decimal("0.5") * data_score
        + Decimal("0.5") * consistency_score
    )

    return confidence_level.quantize(Decimal("0.01"))


def determine_forecast_status(
    months: int,
    confidence_level: Decimal,
) -> str:
    """
    NO_DATA: no historical months at all.
    LOW_CONFIDENCE: history exists but confidence_level is at or
                    below the midpoint of its own [0, 100] range.
    READY: history exists and confidence_level is above that
           midpoint.
    """

    if months == 0:
        return "NO_DATA"

    if confidence_level <= Decimal("50.00"):
        return "LOW_CONFIDENCE"

    return "READY"


def calculate_forecast(
    monthly_historical_demand: dict[int, list[dict]],
) -> dict[int, dict]:
    """
    Compute a next-period forecast per product from its monthly
    historical demand series (as produced by
    get_monthly_historical_demand()).

    n == 0: predicted_demand = 0, trend = NO_DATA
    n == 1: predicted_demand = m1 (flat carry-forward), trend = STABLE
    n >= 2: avg_delta = (mn - m1) / (n - 1)
            predicted_demand = max(0, mn + avg_delta)
            trend = INCREASING / DECREASING / STABLE based on avg_delta

    Also attaches confidence_level and forecast_status to each
    product's result. These are internal to the forecast
    calculation result for now - they are not yet exposed through
    the API response or persisted to forecast history.
    """

    forecasts = {}

    for product_id, series in monthly_historical_demand.items():
        quantities = [item["quantity"] for item in series]
        months = len(quantities)

        confidence_level = calculate_confidence_level(quantities)
        forecast_status = determine_forecast_status(
            months,
            confidence_level,
        )

        if months == 0:
            forecasts[product_id] = {
                "historical_quantity": Decimal("0"),
                "forecast_quantity": Decimal("0"),
                "trend": "NO_DATA",
                "confidence_level": confidence_level,
                "forecast_status": forecast_status,
            }
            continue

        latest_quantity = quantities[-1]

        if months == 1:
            forecasts[product_id] = {
                "historical_quantity": latest_quantity,
                "forecast_quantity": latest_quantity,
                "trend": "STABLE",
                "confidence_level": confidence_level,
                "forecast_status": forecast_status,
            }
            continue

        first_quantity = quantities[0]

        avg_delta = (
            latest_quantity - first_quantity
        ) / Decimal(months - 1)

        if avg_delta > 0:
            trend = "INCREASING"
        elif avg_delta < 0:
            trend = "DECREASING"
        else:
            trend = "STABLE"

        forecast_quantity = latest_quantity + avg_delta

        if forecast_quantity < Decimal("0"):
            forecast_quantity = Decimal("0")

        forecasts[product_id] = {
            "historical_quantity": latest_quantity,
            "forecast_quantity": forecast_quantity,
            "trend": trend,
            "confidence_level": confidence_level,
            "forecast_status": forecast_status,
        }

    return forecasts

def get_forecast(
    db: Session,
) -> dict:
    monthly_historical_demand = get_monthly_historical_demand(db)
    forecasts = calculate_forecast(
        monthly_historical_demand
    )

    products_statement = (
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.id)
    )

    products = list(
        db.scalars(products_statement).all()
    )

    forecast_products = []

    for product in products:
        forecast = forecasts.get(
            product.id,
            {
                "historical_quantity": Decimal("0"),
                "forecast_quantity": Decimal("0"),
                "trend": "NO_DATA",
                "confidence_level": Decimal("0.00"),
                "forecast_status": "NO_DATA",
            },
        )

        forecast_products.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "historical_quantity": forecast[
                    "historical_quantity"
                ],
                "forecast_quantity": forecast[
                    "forecast_quantity"
                ],
                "trend": forecast["trend"],
                "confidence_level": forecast[
                    "confidence_level"
                ],
                "forecast_status": forecast[
                    "forecast_status"
                ],
            }
        )

    return {
        "forecast_period": "NEXT_CYCLE",
        "products": forecast_products,
    }

def generate_forecast(
    db: Session,
) -> dict:
    forecast = get_forecast(db)

    save_forecast_history(
        db,
        forecast,
    )

    return forecast


POINT_TYPE_SALE = "SALE"
POINT_TYPE_PRODUCTION = "PRODUCTION"
POINT_TYPE_FORECAST = "FORECAST"

# A production event on the same calendar day as a sale sorts first:
# the units have to exist before they can be sold, and a fixed
# tie-break is what keeps the x-axis order identical across requests
# (the chart uses the series order as its category domain).
_POINT_TYPE_SORT_RANK = {
    POINT_TYPE_PRODUCTION: 0,
    POINT_TYPE_SALE: 1,
}


def _timeseries_sort_key(point: dict) -> tuple:
    return (
        point["period"],
        _POINT_TYPE_SORT_RANK[point["point_type"]],
        point["application_id"]
        or point["transaction_id"]
        or 0,
    )


def get_forecast_timeseries(
    db: Session,
    product_id: int | None = None,
) -> dict:
    """
    Build a chart series per product with one historical point per
    qualifying sales transaction
    (get_transaction_historical_demand()), followed by exactly one
    forecast point (calculate_forecast()'s predicted_demand for
    that same product). No historical/forecast values are
    recalculated here - both come straight from the shared data
    layers.

    Historical points come from two independent sources, merged onto
    one chronological axis: one SALE point per qualifying sales
    transaction (get_transaction_historical_demand()) and one
    PRODUCTION point per applied ledger entry
    (get_production_event_series()). Sales are authoritative for
    quantity SOLD, the ledger is authoritative for quantity PRODUCED,
    and neither is ever derived from the other - which is why
    production shows up with no sale recorded, and why several sales
    drawn from one applied batch cannot report that batch twice.

    The forecast is still computed from monthly SOLD totals only
    (calculate_forecast() over get_monthly_historical_demand()), never
    re-derived from either series. The single trailing FORECAST point
    is anchored on the month after the product's latest event of
    either kind, so it always sorts last; with no ledger rows that is
    the last transaction month, exactly as before this feature
    existed. A product with no events at all has no historical points
    and its forecast point falls on the month after today.
    """

    monthly_historical_demand = get_monthly_historical_demand(db)
    forecasts = calculate_forecast(monthly_historical_demand)
    historical_transactions = get_transaction_historical_demand(db)
    production_events = get_production_event_series(db)

    products_statement = (
        select(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.id)
    )

    if product_id is not None:
        products_statement = products_statement.where(
            Product.id == product_id
        )

    products = list(db.scalars(products_statement).all())

    today = date.today()

    product_series = []

    for product in products:
        history = historical_transactions.get(product.id, [])
        production = production_events.get(product.id, [])
        forecast = forecasts.get(
            product.id,
            {"forecast_quantity": Decimal("0")},
        )

        sale_points = [
            {
                "period": item["period"],
                "point_type": POINT_TYPE_SALE,
                "transaction_id": item["transaction_id"],
                "transaction_number": item[
                    "transaction_number"
                ],
                "application_id": None,
                "application_number": None,
                "production_cycle_id": None,
                "historical_sales": item["quantity"],
                "quantity_produced": item[
                    "quantity_produced"
                ],
                "predicted_demand": None,
                "is_forecast": False,
            }
            for item in history
        ]

        production_points = [
            {
                "period": event["period"],
                "point_type": POINT_TYPE_PRODUCTION,
                "transaction_id": None,
                "transaction_number": None,
                "application_id": event["application_id"],
                "application_number": event[
                    "application_number"
                ],
                "production_cycle_id": event[
                    "production_cycle_id"
                ],
                "historical_sales": None,
                "quantity_produced": event[
                    "quantity_produced"
                ],
                "predicted_demand": None,
                "is_forecast": False,
            }
            for event in production
        ]

        points = sorted(
            production_points + sale_points,
            key=_timeseries_sort_key,
        )

        if points:
            last_year, last_month = (
                int(part)
                for part in points[-1]["period"].split("-")[:2]
            )
            forecast_year, forecast_month = _next_month(
                last_year,
                last_month,
            )
        else:
            forecast_year, forecast_month = _next_month(
                today.year,
                today.month,
            )

        points.append(
            {
                "period": (
                    f"{forecast_year:04d}-{forecast_month:02d}-01"
                ),
                "point_type": POINT_TYPE_FORECAST,
                "transaction_id": None,
                "transaction_number": None,
                "application_id": None,
                "application_number": None,
                "production_cycle_id": None,
                "historical_sales": None,
                "quantity_produced": None,
                "predicted_demand": forecast[
                    "forecast_quantity"
                ],
                "is_forecast": True,
            }
        )

        product_series.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "series": points,
            }
        )

    return {"products": product_series}