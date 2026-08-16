from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.forecast_history import save_forecast_history

from app.database.models import (
    Product,
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


def get_forecast_timeseries(
    db: Session,
    product_id: int | None = None,
) -> dict:
    """
    Build a monthly chart series per product: one point per
    historical month (reusing get_monthly_historical_demand()'s
    already zero-filled series), followed by exactly one forecast
    point (reusing calculate_forecast()'s predicted_demand for that
    same product). No historical/forecast values are recalculated
    here - both come straight from the shared Phase A/B/C functions.

    The forecast point's period is the calendar month immediately
    after the product's own last historical month. A product with
    no history at all has no historical points, and its forecast
    point falls on the month immediately after today (there is no
    historical month to anchor to).
    """

    monthly_historical_demand = get_monthly_historical_demand(db)
    forecasts = calculate_forecast(monthly_historical_demand)

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
        history = monthly_historical_demand.get(product.id, [])
        forecast = forecasts.get(
            product.id,
            {"forecast_quantity": Decimal("0")},
        )

        points = [
            {
                "period": item["period"],
                "historical_sales": item["quantity"],
                "predicted_demand": None,
                "is_forecast": False,
            }
            for item in history
        ]

        if history:
            last_year, last_month = (
                int(part)
                for part in history[-1]["period"].split("-")
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
                    f"{forecast_year:04d}-{forecast_month:02d}"
                ),
                "historical_sales": None,
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