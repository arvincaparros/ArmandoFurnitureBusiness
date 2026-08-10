import pytest

from fastapi.testclient import TestClient

from main import app
from app.database.connection import SessionLocal

from datetime import datetime
from decimal import Decimal

from app.database.models import (
    CycleResource,
    Product,
    ProductResourceRequirement,
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
def test_resources(db):
    resources = [
        Resource(
            name="Test Wood",
            resource_type="material",
            unit="kg",
            is_active=True,
        ),
        Resource(
            name="Test Epoxy",
            resource_type="material",
            unit="kg",
            is_active=True,
        ),
        Resource(
            name="Test Nails",
            resource_type="material",
            unit="kg",
            is_active=True,
        ),
        Resource(
            name="Test Labor",
            resource_type="labor",
            unit="hours",
            is_active=True,
        ),
    ]

    db.add_all(resources)
    db.commit()

    for resource in resources:
        db.refresh(resource)

    try:
        yield resources

    finally:
        for resource in resources:
            db.delete(resource)

        db.commit()

@pytest.fixture
def test_products(db):
    products = [
        Product(
            name="Test Dining Table",
            selling_price=Decimal("12500.00"),
            is_active=True,
        ),
        Product(
            name="Test Chair",
            selling_price=Decimal("3500.00"),
            is_active=True,
        ),
        Product(
            name="Test Bed Frame",
            selling_price=Decimal("15000.00"),
            is_active=True,
        ),
    ]

    db.add_all(products)
    db.commit()

    for product in products:
        db.refresh(product)

    try:
        yield products

    finally:
        for product in products:
            db.delete(product)

        db.commit()

@pytest.fixture
def test_product_resource_requirements(
    db,
    test_products,
    test_resources,
):
    products = {
        product.name: product
        for product in test_products
    }

    resources = {
        resource.name: resource
        for resource in test_resources
    }

    requirements = [
        # Dining Table
        ProductResourceRequirement(
            product_id=products["Test Dining Table"].id,
            resource_id=resources["Test Wood"].id,
            quantity_required=Decimal("45.0000"),
        ),
        ProductResourceRequirement(
            product_id=products["Test Dining Table"].id,
            resource_id=resources["Test Epoxy"].id,
            quantity_required=Decimal("0.3000"),
        ),
        ProductResourceRequirement(
            product_id=products["Test Dining Table"].id,
            resource_id=resources["Test Nails"].id,
            quantity_required=Decimal("0.3000"),
        ),
        ProductResourceRequirement(
            product_id=products["Test Dining Table"].id,
            resource_id=resources["Test Labor"].id,
            quantity_required=Decimal("36.0000"),
        ),

        # Chair
        ProductResourceRequirement(
            product_id=products["Test Chair"].id,
            resource_id=resources["Test Wood"].id,
            quantity_required=Decimal("12.0000"),
        ),
        ProductResourceRequirement(
            product_id=products["Test Chair"].id,
            resource_id=resources["Test Epoxy"].id,
            quantity_required=Decimal("0.5000"),
        ),
        ProductResourceRequirement(
            product_id=products["Test Chair"].id,
            resource_id=resources["Test Nails"].id,
            quantity_required=Decimal("0.1500"),
        ),
        ProductResourceRequirement(
            product_id=products["Test Chair"].id,
            resource_id=resources["Test Labor"].id,
            quantity_required=Decimal("8.0000"),
        ),

        # Bed Frame
        ProductResourceRequirement(
            product_id=products["Test Bed Frame"].id,
            resource_id=resources["Test Wood"].id,
            quantity_required=Decimal("55.0000"),
        ),
        ProductResourceRequirement(
            product_id=products["Test Bed Frame"].id,
            resource_id=resources["Test Nails"].id,
            quantity_required=Decimal("0.4000"),
        ),
        ProductResourceRequirement(
            product_id=products["Test Bed Frame"].id,
            resource_id=resources["Test Labor"].id,
            quantity_required=Decimal("40.0000"),
        ),
    ]

    db.add_all(requirements)
    db.commit()

    try:
        yield requirements

    finally:
        for requirement in requirements:
            db.delete(requirement)

        db.commit()

@pytest.fixture
def optimization_cycle(
    db,
    test_resources,
    test_products,
    test_product_resource_requirements,
):
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
        "Test Wood": Decimal("1250.0000"),
        "Test Epoxy": Decimal("8.0000"),
        "Test Nails": Decimal("100.0000"),
        "Test Labor": Decimal("576.0000"),
    }

    unit_prices = {
        "Test Wood": Decimal("84.0000"),
        "Test Epoxy": Decimal("650.0000"),
        "Test Nails": Decimal("120.0000"),
        "Test Labor": Decimal("150.0000"),
    }

    for resource in test_resources:
        cycle_resource = CycleResource(
            production_cycle_id=cycle.id,
            resource_id=resource.id,
            available_quantity=available_quantities[
                resource.name
            ],
            unit_price=unit_prices[
                resource.name
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