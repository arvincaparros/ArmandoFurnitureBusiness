import pytest

from fastapi.testclient import TestClient

from main import app
from app.database.connection import SessionLocal

from datetime import datetime
from decimal import Decimal

from app.database.models import (
    CycleResource,
    ProductionCycle,
    Resource,
)

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def optimization_cycle(db):
    cycle = ProductionCycle(
        cycle_date=datetime(2026, 8, 9),
        start_date=datetime(2026, 8, 9),
        end_date=datetime(2026, 8, 9),
        status="PLANNED",
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    available_quantities = {
        1: Decimal("1250.0000"),
        2: Decimal("8.0000"),
        3: Decimal("100.0000"),
        4: Decimal("576.0000"),
    }

    unit_prices = {
        1: Decimal("84.0000"),
        2: Decimal("650.0000"),
        3: Decimal("120.0000"),
        4: Decimal("150.0000"),
    }

    resources = (
        db.query(Resource)
        .order_by(Resource.id)
        .all()
    )

    for resource in resources:
        if resource.id not in available_quantities:
            continue

        cycle_resource = CycleResource(
            production_cycle_id=cycle.id,
            resource_id=resource.id,
            available_quantity=available_quantities[
                resource.id
            ],
            unit_price=unit_prices[
                resource.id
            ],
        )

        db.add(cycle_resource)

    db.commit()
    db.refresh(cycle)

    try:
        yield cycle

    finally:
        db.query(CycleResource).filter(
            CycleResource.production_cycle_id == cycle.id
        ).delete(
            synchronize_session=False
        )

        db.delete(cycle)
        db.commit()