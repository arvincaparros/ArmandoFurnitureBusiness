from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.forecast_history import save_forecast_history
from app.services.opening_inventory import (
    get_reviewed_opening_inventory_set,
)

from app.database.models import (
    Product,
    ProductionApplication,
    ProductionApplicationItem,
    SalesTransaction,
)

# Number of weekly forecast points the timeseries endpoint produces -
# the forecast table and chart both render exactly this many.
WEEKLY_FORECAST_WEEKS = 3


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1

    return year, month + 1


def _week_start(moment: date | datetime) -> date:
    """
    Monday of the calendar week containing `moment` - the weekly
    aggregation's date boundary, used identically for historical
    buckets and forecast week periods so both line up.
    """

    day = moment.date() if isinstance(moment, datetime) else moment

    return day - timedelta(days=day.weekday())


def _next_week(week_start: date) -> date:
    return week_start + timedelta(days=7)


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


def get_weekly_historical_demand(
    db: Session,
) -> dict[int, list[dict]]:
    """
    Aggregate qualifying sales transactions into a chronological,
    zero-filled WEEKLY (Monday-start) SOLD series per active product.

    Produced figures are NOT part of this series - see
    get_weekly_produced_demand() for why quantity_produced is no
    longer summed from SalesTransaction here: that column is stale
    for any post-rollout sale, whose real production lives in the
    ledger instead.

    Qualification matches get_monthly_historical_demand() exactly
    (active product, quantity > 0).

    Returns, per product_id, a list of {"period": "YYYY-MM-DD",
    "quantity": Decimal} covering every calendar week (by its Monday
    start date) from that product's first to last qualifying
    transaction week, in ascending order, with weeks that have no
    qualifying transactions filled in as zero.
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

    weekly_totals: dict[int, dict[date, Decimal]] = defaultdict(dict)

    for row in rows:
        week_key = _week_start(row.transaction_date)

        weekly_totals[row.product_id][week_key] = (
            weekly_totals[row.product_id].get(
                week_key, Decimal("0"),
            )
            + row.quantity
        )

    weekly_series: dict[int, list[dict]] = {}

    for product_id, totals_by_week in weekly_totals.items():
        weeks = sorted(totals_by_week.keys())
        week = weeks[0]
        last_week = weeks[-1]
        series = []

        while week <= last_week:
            series.append(
                {
                    "period": week.strftime("%Y-%m-%d"),
                    "quantity": totals_by_week.get(
                        week, Decimal("0"),
                    ),
                }
            )
            week = _next_week(week)

        weekly_series[product_id] = series

    return weekly_series


def get_weekly_produced_demand(
    db: Session,
) -> dict[int, list[dict]]:
    """
    Aggregate production into a chronological, WEEKLY (Monday-start)
    PRODUCED series per active product - the production counterpart
    of get_weekly_historical_demand(), sourced from two places:

    1. production_application_items, grouped by the week its parent
       ProductionApplication was applied (applied_at) - the
       authoritative source for any production recorded after the
       ledger began. Mirrors forecasting's pre-ledger design note:
       never ProductionAllocation (a replaced-on-every-apply plan),
       never SalesTransaction.quantity_produced for these rows.
    2. SalesTransaction.quantity_produced, but ONLY for rows with
       production_cycle_id IS NULL **and** a transaction_date strictly
       before the ledger's own effective date (the currently REVIEWED
       OpeningInventorySet's effective_date - see
       inventory.py::get_available_stock). That second condition is
       required, not cosmetic: a Production Cycle is no longer a
       precondition for recording a sale, so production_cycle_id IS
       NULL by itself no longer means "pre-rollout legacy row" - it
       can now also mean a brand-new sale with no matching cycle,
       whose quantity_produced is the all-time available-stock
       balance at sale time, not a newly-produced delta. Reading that
       into this series would silently and drastically overstate
       production for the week of an ordinary new sale. Gating on the
       effective date keeps this fallback reading only what it was
       always meant to read: production_application_items simply did
       not exist yet for genuinely pre-rollout rows, so their stored
       figure is still the only production record that exists for
       them. With no REVIEWED set at all, nothing can be dated before
       its effective date, so this fallback correctly reads zero rows
       (consistent with sales being refused outright in that state).

    NEVER zero-filled, unlike the sold series: a week with no
    production simply has no entry, so the chart shows no production
    point for it rather than a fabricated zero. Returns, per
    product_id, a list of {"period": "YYYY-MM-DD",
    "quantity_produced": Decimal}, ascending by period.
    """

    application_rows = db.execute(
        select(
            ProductionApplicationItem.product_id,
            ProductionApplicationItem.quantity_produced,
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
    ).all()

    reviewed_set = get_reviewed_opening_inventory_set(db)

    legacy_rows = (
        db.execute(
            select(
                SalesTransaction.product_id,
                SalesTransaction.transaction_date,
                SalesTransaction.quantity_produced,
            )
            .join(
                Product,
                Product.id == SalesTransaction.product_id,
            )
            .where(
                Product.is_active.is_(True),
                SalesTransaction.production_cycle_id.is_(None),
                SalesTransaction.quantity_produced > 0,
                SalesTransaction.transaction_date
                < reviewed_set.effective_date,
            )
        ).all()
        if reviewed_set is not None
        else []
    )

    weekly_totals: dict[int, dict[date, Decimal]] = defaultdict(dict)

    for row in application_rows:
        week_key = _week_start(row.applied_at)

        weekly_totals[row.product_id][week_key] = (
            weekly_totals[row.product_id].get(
                week_key, Decimal("0"),
            )
            + row.quantity_produced
        )

    for row in legacy_rows:
        week_key = _week_start(row.transaction_date)

        weekly_totals[row.product_id][week_key] = (
            weekly_totals[row.product_id].get(
                week_key, Decimal("0"),
            )
            + row.quantity_produced
        )

    return {
        product_id: [
            {
                "period": week.strftime("%Y-%m-%d"),
                "quantity_produced": quantity,
            }
            for week, quantity in sorted(totals_by_week.items())
        ]
        for product_id, totals_by_week in weekly_totals.items()
    }


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


def _avg_delta_and_trend(
    quantities: list[Decimal],
) -> tuple[Decimal, str]:
    """
    avg_delta = (last - first) / (n - 1) and the INCREASING/
    DECREASING/STABLE label derived from its sign. Shared by
    calculate_forecast() (one next-period step) and
    calculate_weekly_forecast() (several steps applied in a row).
    Callers guarantee len(quantities) >= 2.
    """

    first_quantity = quantities[0]
    latest_quantity = quantities[-1]

    avg_delta = (latest_quantity - first_quantity) / Decimal(
        len(quantities) - 1
    )

    if avg_delta > 0:
        trend = "INCREASING"
    elif avg_delta < 0:
        trend = "DECREASING"
    else:
        trend = "STABLE"

    return avg_delta, trend


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

        avg_delta, trend = _avg_delta_and_trend(quantities)

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


def calculate_weekly_forecast(
    weekly_historical_demand: dict[int, list[dict]],
    num_weeks: int = WEEKLY_FORECAST_WEEKS,
) -> dict[int, dict]:
    """
    Compute the next `num_weeks` weekly forecast points per product
    from its weekly historical demand series (as produced by
    get_weekly_historical_demand()), using the same linear-trend
    extrapolation as calculate_forecast() - just applied
    iteratively, one avg_delta step at a time, instead of a single
    next-period value.

    weeks == 0: every forecast point is 0, trend = NO_DATA
    weeks == 1: every forecast point flat-carries the single
                observed week, trend = STABLE
    weeks >= 2: avg_delta = (last - first) / (weeks - 1)
                forecast[0] = max(0, last + avg_delta)
                forecast[i] = max(0, forecast[i - 1] + avg_delta)

    Also attaches confidence_level and trend, computed once from
    the weekly series and shared by all num_weeks forecast points
    for a product - never recomputed per point.
    """

    forecasts = {}

    for product_id, series in weekly_historical_demand.items():
        quantities = [item["quantity"] for item in series]
        weeks = len(quantities)

        confidence_level = calculate_confidence_level(quantities)

        if weeks == 0:
            forecasts[product_id] = {
                "forecast_quantities": [
                    Decimal("0")
                ] * num_weeks,
                "trend": "NO_DATA",
                "confidence_level": confidence_level,
            }
            continue

        latest_quantity = quantities[-1]

        if weeks == 1:
            forecasts[product_id] = {
                "forecast_quantities": [
                    latest_quantity
                ] * num_weeks,
                "trend": "STABLE",
                "confidence_level": confidence_level,
            }
            continue

        avg_delta, trend = _avg_delta_and_trend(quantities)

        forecast_quantities = []
        previous = latest_quantity

        for _ in range(num_weeks):
            next_value = previous + avg_delta

            if next_value < Decimal("0"):
                next_value = Decimal("0")

            forecast_quantities.append(next_value)
            previous = next_value

        forecasts[product_id] = {
            "forecast_quantities": forecast_quantities,
            "trend": trend,
            "confidence_level": confidence_level,
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

# Production sorts before a same-week sale: the units have to exist
# before they can be sold, and a fixed tie-break keeps the x-axis
# order identical across requests.
_POINT_TYPE_SORT_RANK = {
    POINT_TYPE_PRODUCTION: 0,
    POINT_TYPE_SALE: 1,
}


def get_forecast_timeseries(
    db: Session,
    product_id: int | None = None,
) -> dict:
    """
    Build a weekly series per product merging two independent
    sources onto one chronological axis: one SALE point per calendar
    week of qualifying sold quantity (get_weekly_historical_demand(),
    zero-filled across the product's own first-to-last sold week) and
    one PRODUCTION point per calendar week with any produced quantity
    (get_weekly_produced_demand(), sparse - never zero-filled),
    followed by exactly WEEKLY_FORECAST_WEEKS trailing FORECAST
    points (calculate_weekly_forecast(), sales-only input, unchanged).

    Sales are authoritative for quantity SOLD, the ledger (plus the
    pre-rollout fallback) is authoritative for quantity PRODUCED, and
    neither is ever derived from the other - a week can have a SALE
    point with no PRODUCTION point, a PRODUCTION point with no SALE
    point, both, or neither.

    Forecast week 1 starts the week immediately after the LATER of
    the two series' own last week (so a product produced more
    recently than it last sold still anchors the forecast after that
    production, not stranded mid-series); weeks 2 and 3 follow
    consecutively. A product with no sold history at all still gets a
    forecast, anchored the week after today, exactly as before this
    change.
    """

    weekly_sold = get_weekly_historical_demand(db)
    weekly_produced = get_weekly_produced_demand(db)
    forecasts = calculate_weekly_forecast(weekly_sold)

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

    today_week_start = _week_start(date.today())

    product_series = []

    for product in products:
        sold_weeks = weekly_sold.get(product.id, [])
        produced_weeks = weekly_produced.get(product.id, [])

        forecast = forecasts.get(
            product.id,
            {
                "forecast_quantities": [
                    Decimal("0")
                ] * WEEKLY_FORECAST_WEEKS,
                "trend": "NO_DATA",
                "confidence_level": Decimal("0.00"),
            },
        )

        points = [
            {
                "period": item["period"],
                "point_type": POINT_TYPE_SALE,
                "historical_sales": item["quantity"],
                "quantity_produced": None,
                "predicted_demand": None,
                "is_forecast": False,
            }
            for item in sold_weeks
        ] + [
            {
                "period": item["period"],
                "point_type": POINT_TYPE_PRODUCTION,
                "historical_sales": None,
                "quantity_produced": item["quantity_produced"],
                "predicted_demand": None,
                "is_forecast": False,
            }
            for item in produced_weeks
        ]

        points.sort(
            key=lambda point: (
                point["period"],
                _POINT_TYPE_SORT_RANK[point["point_type"]],
            )
        )

        last_week = (
            date.fromisoformat(points[-1]["period"])
            if points
            else today_week_start
        )

        week = _next_week(last_week)

        for forecast_quantity in forecast["forecast_quantities"]:
            points.append(
                {
                    "period": week.strftime("%Y-%m-%d"),
                    "point_type": POINT_TYPE_FORECAST,
                    "historical_sales": None,
                    "quantity_produced": None,
                    "predicted_demand": forecast_quantity,
                    "is_forecast": True,
                }
            )
            week = _next_week(week)

        product_series.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "trend": forecast["trend"],
                "confidence_level": forecast["confidence_level"],
                "series": points,
            }
        )

    return {"products": product_series}