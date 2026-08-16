from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.database.models import (
    OptimizationRun,
    ProductionAllocation,
    ProductionCycle,
)

from app.database.models import SalesTransaction


def test_dashboard_summary_with_test_data(
    client,
    db,
    optimization_cycle,
    test_products,
):
    response = client.get(
        "/api/dashboard/summary"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_products"] >= 3
    assert data["total_resources"] >= 4
    assert data["total_production_cycles"] >= 1


def test_dashboard_summary_counts_allocations(
    client,
    db,
    optimization_cycle,
    test_products,
):
    allocation = ProductionAllocation(
        production_cycle_id=optimization_cycle.id,
        product_id=test_products[1].id,
        quantity=Decimal("12.0000"),
    )

    db.add(allocation)
    db.commit()

    try:
        response = client.get(
            "/api/dashboard/summary"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["total_allocations"] >= 1

    finally:
        db.delete(allocation)
        db.commit()

def test_dashboard_summary_latest_optimization(
    client,
    db,
    optimization_cycle,
):
    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={
            "objective": "MAX_PROFIT",
        },
    )

    assert optimize_response.status_code == 200

    response = client.get(
        "/api/dashboard/summary"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_optimization_runs"] >= 1
    assert data["latest_optimization_profit"] is not None

def _make_older_cycle(db):
    """
    A cycle guaranteed to sort before `optimization_cycle` (and
    before any real seeded cycle) in the created_at DESC, id DESC
    canonical ordering - explicit past created_at, same pattern used
    in test_production_cycles.py, rather than relying on insertion
    timing.
    """

    cycle = ProductionCycle(
        cycle_date=datetime(2020, 1, 1),
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2020, 1, 1),
        status="COMPLETED",
        created_at=datetime(2020, 1, 1),
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    return cycle


def _make_optimal_run(db, cycle_id, started_at, total_profit):
    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=started_at,
        completed_at=started_at,
        duration_ms=0,
        status="OPTIMAL",
        objective_value=total_profit,
        total_profit=total_profit,
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run


def test_dashboard_summary_profit_matches_latest_cycle_optimal_run(
    client,
    db,
    optimization_cycle,
    test_products,
):
    """
    Scenario 1 + 4: the latest cycle has a real OPTIMAL run (via the
    actual /optimize endpoint, not a manual insert) - dashboard
    profit must equal that run's own total_profit exactly, not just
    "is not None".
    """

    optimize_response = client.post(
        f"/api/production-cycles/{optimization_cycle.id}/optimize",
        json={"objective": "MAX_PROFIT"},
    )

    assert optimize_response.status_code == 200

    run = db.scalars(
        select(OptimizationRun).where(
            OptimizationRun.production_cycle_id
            == optimization_cycle.id
        )
    ).one()

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200

    data = response.json()

    assert Decimal(
        data["latest_optimization_profit"]
    ) == run.total_profit


def test_dashboard_summary_profit_null_when_latest_cycle_has_no_run(
    client,
    db,
    optimization_cycle,
):
    """
    Scenario 2: an older cycle has an OPTIMAL run, but the canonical
    latest cycle (optimization_cycle, created just now) does not -
    dashboard profit must be null, never the older cycle's profit.
    """

    older_cycle = _make_older_cycle(db)

    try:
        _make_optimal_run(
            db,
            older_cycle.id,
            datetime(2020, 1, 1, 12, 0),
            Decimal("999.0000"),
        )

        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200

        data = response.json()

        assert data["latest_optimization_profit"] is None

    finally:
        db.query(OptimizationRun).filter(
            OptimizationRun.production_cycle_id
            == older_cycle.id
        ).delete(synchronize_session=False)

        db.delete(older_cycle)
        db.commit()


def test_dashboard_summary_profit_ignores_older_cycle_when_latest_has_own_run(
    client,
    db,
    optimization_cycle,
):
    """
    Scenario 3: OPTIMAL runs exist for both an older cycle and the
    canonical latest cycle, with different profits - dashboard must
    return the latest cycle's profit only.
    """

    older_cycle = _make_older_cycle(db)

    try:
        _make_optimal_run(
            db,
            older_cycle.id,
            datetime(2020, 1, 1, 12, 0),
            Decimal("111.0000"),
        )

        _make_optimal_run(
            db,
            optimization_cycle.id,
            datetime(2026, 8, 9, 12, 0),
            Decimal("222.0000"),
        )

        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200

        data = response.json()

        assert Decimal(
            data["latest_optimization_profit"]
        ) == Decimal("222.0000")

    finally:
        db.query(OptimizationRun).filter(
            OptimizationRun.production_cycle_id.in_(
                [older_cycle.id, optimization_cycle.id]
            )
        ).delete(synchronize_session=False)

        db.delete(older_cycle)
        db.commit()


def test_dashboard_summary_profit_uses_newest_run_within_latest_cycle(
    client,
    db,
    optimization_cycle,
):
    """
    Same-cycle behavior: two OPTIMAL runs exist for the same
    (latest) cycle - dashboard must use the newer one.
    """

    _make_optimal_run(
        db,
        optimization_cycle.id,
        datetime(2026, 8, 9, 8, 0),
        Decimal("50.0000"),
    )

    _make_optimal_run(
        db,
        optimization_cycle.id,
        datetime(2026, 8, 9, 9, 0),
        Decimal("75.0000"),
    )

    try:
        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200

        data = response.json()

        assert Decimal(
            data["latest_optimization_profit"]
        ) == Decimal("75.0000")

    finally:
        db.query(OptimizationRun).filter(
            OptimizationRun.production_cycle_id
            == optimization_cycle.id
        ).delete(synchronize_session=False)

        db.commit()


def test_dashboard_summary_sales_totals(
    client,
    db,
    test_products,
):
    transactions = [
        SalesTransaction(
            transaction_number="TRX-TEST-001",
            quantity_produced=Decimal("2.0000"),
            production_cost=Decimal("2551.0000"),
            product_id=test_products[0].id,
            transaction_date=datetime(2026, 8, 10, 10, 0),
            quantity=Decimal("2.0000"),
            unit_price=Decimal("3500.00"),
            total_sales=Decimal("7000.00"),
            unit_profit=Decimal("949.0000"),
            total_profit=Decimal("1898.0000"),
        ),
        SalesTransaction(
            transaction_number="TRX-TEST-002",
            quantity_produced=Decimal("2.0000"),
            production_cost=Decimal("2551.0000"),
            product_id=test_products[1].id,
            transaction_date=datetime(2026, 8, 10, 11, 0),
            quantity=Decimal("3.0000"),
            unit_price=Decimal("5000.00"),
            total_sales=Decimal("15000.00"),
            unit_profit=Decimal("1200.0000"),
            total_profit=Decimal("3600.0000"),
        ),
    ]

    db.add_all(transactions)
    db.commit()

    try:
        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200

        data = response.json()

        assert Decimal(data["total_sales"]) == Decimal("22000.00")
        assert Decimal(data["total_sales_profit"]) == Decimal("5498.0000")

    finally:
        for transaction in transactions:
            db.delete(transaction)

        db.commit()

def test_dashboard_summary_latest_forecast(
    client,
    db,
):
    from app.services.forecast_history import (
        save_forecast_history,
    )
    from app.services.forecasting import get_forecast

    forecast = get_forecast(db)
    run = save_forecast_history(db, forecast)

    try:
        response = client.get("/api/dashboard/summary")

        assert response.status_code == 200

        data = response.json()

        assert data["latest_forecast_period"] == (
            "NEXT_CYCLE"
        )

        assert data["latest_forecast_created_at"] is not None

        expected_total = sum(
            item["forecast_quantity"]
            for item in forecast["products"]
        )

        assert Decimal(
            data["latest_forecast_total_quantity"]
        ) == expected_total

    finally:
        db.delete(run)
        db.commit()