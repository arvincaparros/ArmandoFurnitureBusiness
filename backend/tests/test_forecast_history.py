from datetime import datetime
from decimal import Decimal

from app.database.models import (
    ForecastResult,
    ForecastRun,
)

from app.services.forecast_history import (
    get_forecast_history,
    get_forecast_history_run,
    get_latest_forecast_history_run,
    save_forecast_history,
)


def create_test_forecast(test_products):
    return {
        "forecast_period": "NEXT_CYCLE",
        "products": [
            {
                "product_id": test_products[0].id,
                "product_name": test_products[0].name,
                "historical_quantity": Decimal("10.0000"),
                "forecast_quantity": Decimal("12.0000"),
                "trend": "INCREASING",
            },
            {
                "product_id": test_products[1].id,
                "product_name": test_products[1].name,
                "historical_quantity": Decimal("8.0000"),
                "forecast_quantity": Decimal("8.0000"),
                "trend": "STABLE",
            },
        ],
    }


def test_save_forecast_history(
    db,
    test_products,
):
    forecast = create_test_forecast(test_products)

    run = save_forecast_history(
        db,
        forecast,
    )

    try:
        assert run.id is not None
        assert run.forecast_period == "NEXT_CYCLE"
        assert run.created_at is not None

        results = (
            db.query(ForecastResult)
            .filter(
                ForecastResult.forecast_run_id
                == run.id
            )
            .order_by(ForecastResult.product_id)
            .all()
        )

        assert len(results) == 2

        assert results[0].product_id == test_products[0].id
        assert results[0].historical_quantity == Decimal(
            "10.0000"
        )
        assert results[0].forecast_quantity == Decimal(
            "12.0000"
        )
        assert results[0].trend == "INCREASING"

        assert results[1].product_id == test_products[1].id
        assert results[1].historical_quantity == Decimal(
            "8.0000"
        )
        assert results[1].forecast_quantity == Decimal(
            "8.0000"
        )
        assert results[1].trend == "STABLE"

    finally:
        db.delete(run)
        db.commit()


def test_get_forecast_history(
    db,
    test_products,
):
    forecast = create_test_forecast(test_products)

    first_run = save_forecast_history(
        db,
        forecast,
    )

    second_run = save_forecast_history(
        db,
        forecast,
    )

    try:
        history = get_forecast_history(db)

        run_ids = [run.id for run in history]

        assert second_run.id in run_ids
        assert first_run.id in run_ids

        assert run_ids.index(second_run.id) < run_ids.index(
            first_run.id
        )

    finally:
        db.delete(second_run)
        db.delete(first_run)
        db.commit()


def test_get_forecast_history_run(
    db,
    test_products,
):
    forecast = create_test_forecast(test_products)

    run = save_forecast_history(
        db,
        forecast,
    )

    try:
        result = get_forecast_history_run(
            db,
            run.id,
        )

        assert result is not None
        assert result.id == run.id

    finally:
        db.delete(run)
        db.commit()


def test_get_forecast_history_run_not_found(db):
    result = get_forecast_history_run(
        db,
        999999,
    )

    assert result is None


def test_get_latest_forecast_history_run(
    db,
    test_products,
):
    forecast = create_test_forecast(test_products)

    first_run = save_forecast_history(
        db,
        forecast,
    )

    second_run = save_forecast_history(
        db,
        forecast,
    )

    try:
        latest = get_latest_forecast_history_run(db)

        assert latest is not None
        assert latest.id == second_run.id

    finally:
        db.delete(second_run)
        db.delete(first_run)
        db.commit()