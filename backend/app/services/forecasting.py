from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Product,
    SalesTransaction,
)


def get_historical_demand(
    db: Session,
) -> dict[int, list[Decimal]]:
    statement = (
        select(
            SalesTransaction.product_id,
            SalesTransaction.quantity,
        )
        .where(
            SalesTransaction.quantity > 0,
        )
        .order_by(
            SalesTransaction.transaction_date,
            SalesTransaction.id,
        )
    )

    rows = db.execute(statement).all()

    historical_demand = defaultdict(list)

    for row in rows:
        historical_demand[row.product_id].append(
            row.quantity
        )

    return dict(historical_demand)

def calculate_forecast(
    historical_demand: dict[int, list[Decimal]],
) -> dict[int, dict]:
    forecasts = {}

    for product_id, quantities in historical_demand.items():
        if not quantities:
            forecasts[product_id] = {
                "historical_quantity": Decimal("0"),
                "forecast_quantity": Decimal("0"),
                "trend": "NO_DATA",
            }
            continue

        latest_quantity = quantities[-1]

        if len(quantities) == 1:
            forecasts[product_id] = {
                "historical_quantity": latest_quantity,
                "forecast_quantity": latest_quantity,
                "trend": "STABLE",
            }
            continue

        previous_quantity = quantities[-2]

        if latest_quantity > previous_quantity:
            trend = "INCREASING"
        elif latest_quantity < previous_quantity:
            trend = "DECREASING"
        else:
            trend = "STABLE"

        forecasts[product_id] = {
            "historical_quantity": latest_quantity,
            "forecast_quantity": latest_quantity,
            "trend": trend,
        }

    return forecasts

def get_forecast(
    db: Session,
) -> dict:
    historical_demand = get_historical_demand(db)
    forecasts = calculate_forecast(
        historical_demand
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
            }
        )

    return {
        "forecast_period": "NEXT_CYCLE",
        "products": forecast_products,
    }