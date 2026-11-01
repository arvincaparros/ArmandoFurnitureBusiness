from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.forecast_history import save_forecast_history

from app.database.models import (
    Product,
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
    zero-filled WEEKLY (Monday-start) demand series per active
    product.

    This is the shared historical data layer for the forecast
    table and the forecast chart - both render from the same
    series produced here, via get_forecast_timeseries(), so the
    two never recompute or disagree on weekly totals.

    Qualification matches get_monthly_historical_demand() exactly
    (active product, quantity > 0).

    Returns, per product_id, a list of
    {"period": "YYYY-MM-DD", "quantity": Decimal,
     "quantity_produced": Decimal} covering every calendar week
    (by its Monday start date) from that product's first to last
    qualifying transaction week, in ascending order, with weeks
    that have no qualifying transactions filled in as zero.
    """

    statement = (
        select(
            SalesTransaction.product_id,
            SalesTransaction.transaction_date,
            SalesTransaction.quantity,
            SalesTransaction.quantity_produced,
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

    weekly_totals: dict[int, dict[date, dict[str, Decimal]]] = (
        defaultdict(dict)
    )

    for row in rows:
        week_key = _week_start(row.transaction_date)

        totals = weekly_totals[row.product_id].setdefault(
            week_key,
            {
                "quantity": Decimal("0"),
                "quantity_produced": Decimal("0"),
            },
        )

        totals["quantity"] += row.quantity
        totals["quantity_produced"] += row.quantity_produced

    weekly_series: dict[int, list[dict]] = {}

    for product_id, totals_by_week in weekly_totals.items():
        weeks = sorted(totals_by_week.keys())

        week = weeks[0]
        last_week = weeks[-1]

        series = []

        while week <= last_week:
            totals = totals_by_week.get(
                week,
                {
                    "quantity": Decimal("0"),
                    "quantity_produced": Decimal("0"),
                },
            )

            series.append(
                {
                    "period": week.strftime("%Y-%m-%d"),
                    "quantity": totals["quantity"],
                    "quantity_produced": totals[
                        "quantity_produced"
                    ],
                }
            )

            week = _next_week(week)

        weekly_series[product_id] = series

    return weekly_series


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


def get_forecast_timeseries(
    db: Session,
    product_id: int | None = None,
) -> dict:
    """
    Build a weekly series per product with one historical point
    per calendar week of qualifying sales transactions
    (get_weekly_historical_demand(), zero-filled from the
    product's first to last qualifying week), followed by exactly
    WEEKLY_FORECAST_WEEKS forecast points (calculate_weekly_
    forecast() for that same product). No historical/forecast
    values are recalculated here - both come straight from the
    shared data layers, and this one series is the single source
    the forecast table and the forecast chart both render from.

    Forecast week 1 starts the week immediately after the
    product's own latest historical week, so it always sorts
    after the last historical point; weeks 2 and 3 follow
    consecutively. A product with no history has no historical
    points, and week 1 falls on the week immediately after today's
    (there is no transaction date to anchor to).
    """

    weekly_historical_demand = get_weekly_historical_demand(db)
    forecasts = calculate_weekly_forecast(weekly_historical_demand)

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
        history = weekly_historical_demand.get(product.id, [])
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
                "historical_sales": item["quantity"],
                "quantity_produced": item[
                    "quantity_produced"
                ],
                "predicted_demand": None,
                "is_forecast": False,
            }
            for item in history
        ]

        last_week = (
            date.fromisoformat(history[-1]["period"])
            if history
            else today_week_start
        )

        week = _next_week(last_week)

        for forecast_quantity in forecast["forecast_quantities"]:
            points.append(
                {
                    "period": week.strftime("%Y-%m-%d"),
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
                "confidence_level": forecast[
                    "confidence_level"
                ],
                "series": points,
            }
        )

    return {"products": product_series}