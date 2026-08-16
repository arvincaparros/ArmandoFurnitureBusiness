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
    User,
)

from app.services.auth import hash_password


AUTH_TEST_USERNAME = "conftest_auth_user"
AUTH_TEST_PASSWORD = "ConftestAuthPassword9!"


@pytest.fixture(scope="session")
def _shared_auth_test_user():
    """
    Session-scoped so login/hashing happens once for the whole test
    run, not once per test - business tests don't care about the
    identity of the authenticated caller, only that one exists.
    """

    session = SessionLocal()

    session.query(User).filter(
        User.username == AUTH_TEST_USERNAME
    ).delete()
    session.commit()

    user = User(
        username=AUTH_TEST_USERNAME,
        email=f"{AUTH_TEST_USERNAME}@example.com",
        password_hash=hash_password(AUTH_TEST_PASSWORD),
        is_active=True,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    yield user

    session.query(User).filter(
        User.username == AUTH_TEST_USERNAME
    ).delete()
    session.commit()
    session.close()


@pytest.fixture(scope="session")
def auth_token(_shared_auth_test_user):
    login_response = TestClient(app).post(
        "/api/auth/login",
        json={
            "username": AUTH_TEST_USERNAME,
            "password": AUTH_TEST_PASSWORD,
        },
    )

    return login_response.json()["access_token"]


@pytest.fixture
def client(auth_token):
    """
    Pre-authenticated by default so the existing (pre-auth) business
    test suite keeps working without every call site changing.
    Tests that need to exercise unauthenticated behavior should use
    the `unauthenticated_client` fixture instead - a per-call
    `headers={"Authorization": ...}` override still works normally
    for tests that need a *different* token (e.g. an invalid or
    expired one), since per-call headers replace this default.
    """

    test_client = TestClient(app)
    test_client.headers["Authorization"] = f"Bearer {auth_token}"

    return test_client


@pytest.fixture
def unauthenticated_client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def cleanup_test_data(db):
    test_resource_names = [
        "Test Wood",
        "Test Epoxy",
        "Test Nails",
        "Test Labor",
    ]

    test_product_names = [
        "Test Dining Table",
        "Test Chair",
        "Test Bed Frame",
    ]

    # Remove dependent cycle resources first
    db.query(CycleResource).filter(
        CycleResource.resource_id.in_(
            db.query(Resource.id).filter(
                Resource.name.in_(test_resource_names)
            )
        )
    ).delete(
        synchronize_session=False
    )

    # Remove product-resource requirements
    db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.resource_id.in_(
            db.query(Resource.id).filter(
                Resource.name.in_(test_resource_names)
            )
        )
    ).delete(
        synchronize_session=False
    )

    db.query(ProductResourceRequirement).filter(
        ProductResourceRequirement.product_id.in_(
            db.query(Product.id).filter(
                Product.name.in_(test_product_names)
            )
        )
    ).delete(
        synchronize_session=False
    )

    # Remove test production cycles
    db.query(ProductionCycle).filter(
        ProductionCycle.cycle_date == datetime(2026, 8, 9)
    ).delete(
        synchronize_session=False
    )

    # Remove test products
    db.query(Product).filter(
        Product.name.in_(test_product_names)
    ).delete(
        synchronize_session=False
    )

    # Remove test resources
    db.query(Resource).filter(
        Resource.name.in_(test_resource_names)
    ).delete(
        synchronize_session=False
    )

    db.commit()

    yield

@pytest.fixture
def test_resources(db, cleanup_test_data):
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
def test_products(db, cleanup_test_data):
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