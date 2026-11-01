import os
from pathlib import Path

from dotenv import load_dotenv


# --- Test database isolation -------------------------------------------
#
# MUST run before any `app.*` or `main` import below: connection.py
# reads DATABASE_URL at import time, so by the time SessionLocal exists
# the choice of database is already locked in. load_dotenv() inside
# connection.py will NOT override what we set here (override=False is
# its default), so backend/.env's development URL can never win.
#
# The name check is deliberately an exact-match allowlist rather than a
# "not the dev database" denylist: a typo'd database name must abort the
# run, not create a stray database or silently target something else.
_TEST_DATABASE_NAME = "armando_furniture_test"

load_dotenv(
    Path(__file__).resolve().parents[1] / ".env.test",
    override=True,
)

_TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if not _TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is not configured. Copy "
        "backend/.env.test.example to backend/.env.test and set it to "
        f"the {_TEST_DATABASE_NAME} database. Tests must never run "
        "against the development database."
    )

if not _TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0] == (
    _TEST_DATABASE_NAME
):
    raise RuntimeError(
        f"TEST_DATABASE_URL must point at {_TEST_DATABASE_NAME}, got: "
        f"{_TEST_DATABASE_URL.rsplit('/', 1)[-1]}"
    )

os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

import pytest  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from app.database.connection import SessionLocal, engine  # noqa: E402

from datetime import datetime
from decimal import Decimal

from app.database.models import (
    CycleResource,
    OpeningInventoryItem,
    OpeningInventorySet,
    OptimizationRun,
    Product,
    ProductResourceRequirement,
    ProductionApplication,
    ProductionApplicationItem,
    ProductionApplicationResourceItem,
    ProductionCycle,
    Resource,
    SalesTransaction,
    User,
)

from app.services.auth import hash_password
from app.services.production_application import (
    save_production_application,
)


AUTH_TEST_USERNAME = "conftest_auth_user"
AUTH_TEST_PASSWORD = "ConftestAuthPassword9!"


@pytest.fixture(scope="session", autouse=True)
def _require_test_database():
    """
    Second, independent check against the ENGINE that was actually
    built - not just the environment variable the guard above read.
    Catches the case where something imported app.database.connection
    before this module (e.g. a stray plugin or a `-p` hook), which
    would have bound the engine to the development database before our
    os.environ assignment could take effect.
    """

    actual = engine.url.database

    if actual != _TEST_DATABASE_NAME:
        pytest.exit(
            f"Refusing to run: the SQLAlchemy engine is bound to "
            f"'{actual}', not '{_TEST_DATABASE_NAME}'.",
            returncode=3,
        )

    yield


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


# --- Ledger purge ------------------------------------------------------
#
# The append-only ledger tables carry the ONLY ON DELETE RESTRICT
# foreign keys in the schema:
#
#   production_applications.production_cycle_id  -> production_cycles
#   production_applications.optimization_run_id  -> optimization_runs
#   production_application_items.product_id      -> products
#   opening_inventory_items.product_id           -> products
#
# Those four are deliberate and stay exactly as they are: applied
# production history and a reviewed opening balance must never be
# deletable out from under the rows they were recorded against. What
# they mean for tests is that every fixture which deletes a Product,
# Resource or ProductionCycle has to clear the ledger rows pointing at
# it FIRST - otherwise teardown raises IntegrityError and leaks both
# the record it was deleting and everything it had not reached yet.
#
# Hence one shared helper instead of per-module cleanup: the delete
# order lives in a single place, and a new ledger table only has to be
# added to _LEDGER_PURGE_ORDER once.
_LEDGER_PURGE_ORDER = (
    # Children before parents; applications before the cycles and
    # optimization runs they RESTRICT.
    ProductionApplicationResourceItem,
    ProductionApplicationItem,
    ProductionApplication,
    OpeningInventoryItem,
    OpeningInventorySet,
)


# Fixtures allowed to ask for a whole-table wipe. A clean-slate purge
# is correct for a suite that owns the ledger for the duration of its
# test, and wrong everywhere else now that apply_optimization writes
# real ledger rows (Task 6) - which is why `all_rows` is opt-in and
# named rather than being the default.
LEDGER_CLEAN_SLATE_FIXTURES = (
    "cleanup_applications",
    "cleanup_opening_inventory",
)


def purge_ledger(
    db,
    *,
    cycle_ids=None,
    product_ids=None,
    all_rows=False,
):
    """
    Delete production-application and opening-inventory rows in
    FK-safe order, then commit.

    SCOPED BY DEFAULT. Pass `cycle_ids` and/or `product_ids` to remove
    only the rows a fixture owns; pass `all_rows=True` only from one of
    LEDGER_CLEAN_SLATE_FIXTURES. Calling with no scope at all raises -
    a silent whole-table wipe is exactly the accident this signature
    exists to prevent.

    Why scoping became necessary: until Task 6, no service wrote these
    tables, so "every row is test residue" was true and a blanket
    delete was safe. apply_optimization now appends a real ledger row
    on every apply, so a blanket purge from a shared fixture can
    destroy rows another test legitimately created.

    Scope semantics:
      cycle_ids   -> every application in those cycles, deleted whole.
                     A fixture-owned cycle owns everything applied to
                     it, so this is the clean primary scope.
      product_ids -> applications referencing those products, deleted
                     whole (an application stripped of its items would
                     be a corrupt history row, not a tidy one), plus
                     the opening-inventory items declaring those
                     products. An opening-inventory SET is removed only
                     if emptying it left it childless - never because
                     it merely mentioned the product, so a set covering
                     other products survives intact.

    Known edge: an application spanning BOTH an in-scope and an
    out-of-scope product is deleted whole. It cannot survive anyway -
    the in-scope product is about to be deleted and
    production_application_items.product_id is RESTRICT - so the only
    alternative would be leaving a half-stripped parent behind.
    """

    # Most calls land from fixture teardown, where the session may
    # still be in a failed transaction - a test that hit an
    # IntegrityError (several deliberately do) or failed an assert
    # mid-write leaves PostgreSQL refusing every further statement
    # with InFailedSqlTransaction. The first DELETE below would then
    # raise from inside `finally` and replace the real test failure
    # with a confusing teardown error, while leaking the very rows
    # this helper exists to remove.
    #
    # Safe unconditionally: a purge never has uncommitted work of its
    # own worth keeping, and anything a test wanted kept it had to
    # commit before returning anyway. No-op on a clean session.
    db.rollback()

    if all_rows:
        for model in _LEDGER_PURGE_ORDER:
            db.query(model).delete(synchronize_session=False)

        db.commit()

        return

    # A scope that was PASSED but resolved to nothing is a legitimate
    # no-op (cleanup_test_data resolves its ids before the rows it
    # cleans up exist). Passing NO scope at all is the accident this
    # guard is for, so the two cases are distinguished by `is None`
    # rather than by emptiness.
    scope_given = cycle_ids is not None or product_ids is not None

    cycle_ids = list(cycle_ids or ())
    product_ids = list(product_ids or ())

    if not scope_given:
        raise ValueError(
            "purge_ledger needs cycle_ids, product_ids, or an explicit "
            "all_rows=True (permitted only from "
            f"{', '.join(LEDGER_CLEAN_SLATE_FIXTURES)}). Refusing to "
            "wipe both ledgers by accident."
        )

    application_ids = set()

    if cycle_ids:
        application_ids.update(
            row[0]
            for row in db.query(ProductionApplication.id)
            .filter(
                ProductionApplication.production_cycle_id.in_(
                    cycle_ids
                )
            )
            .all()
        )

    if product_ids:
        application_ids.update(
            row[0]
            for row in db.query(
                ProductionApplicationItem.production_application_id
            )
            .filter(
                ProductionApplicationItem.product_id.in_(product_ids)
            )
            .all()
        )

    # Same order as _LEDGER_PURGE_ORDER, filtered rather than
    # reordered: resource items, then product items, then the
    # applications that RESTRICT their cycle and run.
    if application_ids:
        owned = list(application_ids)

        db.query(ProductionApplicationResourceItem).filter(
            ProductionApplicationResourceItem
            .production_application_id.in_(owned)
        ).delete(synchronize_session=False)

        db.query(ProductionApplicationItem).filter(
            ProductionApplicationItem.production_application_id.in_(
                owned
            )
        ).delete(synchronize_session=False)

        db.query(ProductionApplication).filter(
            ProductionApplication.id.in_(owned)
        ).delete(synchronize_session=False)

    if product_ids:
        touched_set_ids = {
            row[0]
            for row in db.query(
                OpeningInventoryItem.opening_inventory_set_id
            )
            .filter(
                OpeningInventoryItem.product_id.in_(product_ids)
            )
            .all()
        }

        db.query(OpeningInventoryItem).filter(
            OpeningInventoryItem.product_id.in_(product_ids)
        ).delete(synchronize_session=False)

        # Only sets this purge actually emptied. A set that still
        # declares other products keeps its row; a set left with no
        # items at all is residue with nothing to say.
        for set_id in touched_set_ids:
            remaining = (
                db.query(OpeningInventoryItem)
                .filter(
                    OpeningInventoryItem.opening_inventory_set_id
                    == set_id
                )
                .count()
            )

            if remaining == 0:
                db.query(OpeningInventorySet).filter(
                    OpeningInventorySet.id == set_id
                ).delete(synchronize_session=False)

    db.commit()


@pytest.fixture
def cleanup_applications(db):
    """
    Was a local fixture in test_production_application.py. Lives here
    now so the application suite, the opening-inventory suite and the
    row-owning fixtures below all purge through the same ordered
    helper rather than three hand-maintained delete sequences.
    """

    purge_ledger(db, all_rows=True)

    yield

    purge_ledger(db, all_rows=True)


@pytest.fixture
def cleanup_opening_inventory(db):
    """
    Was a local fixture in test_opening_inventory.py. Kept as a
    separate name from `cleanup_applications` because the test
    signatures that request it document which ledger the test is
    about; both purge the whole ledger, which is a superset of what
    each used to delete and safe for the reason purge_ledger explains.
    """

    purge_ledger(db, all_rows=True)

    yield

    purge_ledger(db, all_rows=True)


@pytest.fixture
def complete_opening_inventory(client, db):
    """
    A COMPLETE, REVIEWED opening inventory set - the precondition
    Task 23 put in front of every sale (POST /api/transactions is
    refused with 409 without one, ahead of any other validation).

    Dated 2026-01-01 and declaring a single anchor product created
    before it. Completeness is "active products with
    created_at <= effective_date", and every product seeded in
    armando_furniture_test was created later than that, so this one
    declaration makes the set GENUINELY complete rather than merely
    accepted. Completeness semantics themselves are tested directly in
    test_opening_inventory_gate.py.

    Function-scoped on purpose: it must exist before the request under
    test, and must not leak a REVIEWED set into modules that assert
    the gate is CLOSED.
    """

    anchor = Product(
        name="Opening Inventory Anchor Product",
        selling_price=Decimal("1.00"),
        labor_cost=Decimal("0.00"),
        is_active=True,
        created_at=datetime(2025, 1, 1),
    )

    db.add(anchor)
    db.commit()
    db.refresh(anchor)

    inventory_set = OpeningInventorySet(
        set_number="OI-GATEFIX",
        status="DRAFT",
        effective_date=datetime(2026, 1, 1),
    )

    db.add(inventory_set)
    db.flush()

    db.add(
        OpeningInventoryItem(
            opening_inventory_set_id=inventory_set.id,
            product_id=anchor.id,
            quantity=Decimal("0"),
        )
    )

    db.commit()

    review = client.post(
        f"/api/opening-inventory/{inventory_set.id}/review",
    )

    assert review.status_code == 200, review.text

    set_id = inventory_set.id
    anchor_id = anchor.id

    yield inventory_set

    db.rollback()

    db.query(OpeningInventoryItem).filter(
        OpeningInventoryItem.opening_inventory_set_id == set_id
    ).delete(synchronize_session=False)

    db.query(OpeningInventorySet).filter(
        OpeningInventorySet.id == set_id
    ).delete(synchronize_session=False)

    db.query(Product).filter(
        Product.id == anchor_id
    ).delete(synchronize_session=False)

    db.commit()


@pytest.fixture
def two_cycles(db):
    """
    Two back-to-back 7-day cycles, shared by the cycle-resolution tests
    and by any test that needs to POST a sale (Task 8 refuses a sale
    whose date falls in no cycle).

    Under the HALF-OPEN rule they must not overlap: Nov 6 is the first
    cycle's end_date and the second's start_date, and belongs to the
    second only.
    """

    first = ProductionCycle(
        cycle_date=datetime(2026, 10, 30),
        start_date=datetime(2026, 10, 30),
        end_date=datetime(2026, 11, 6),
        status="OPEN",
    )

    second = ProductionCycle(
        cycle_date=datetime(2026, 11, 6),
        start_date=datetime(2026, 11, 6),
        end_date=datetime(2026, 11, 13),
        status="OPEN",
    )

    db.add_all([first, second])
    db.commit()
    db.refresh(first)
    db.refresh(second)

    yield first, second

    db.rollback()

    # Scoped ledger purge FIRST: tests using this fixture apply
    # production into these cycles, and production_applications
    # RESTRICTs optimization_run_id - so the ORM cascade from
    # ProductionCycle.optimization_runs on the deletes below is refused
    # while an application still points at a run. Scoped to these two
    # cycles only.
    purge_ledger(db, cycle_ids=[first.id, second.id])

    db.query(SalesTransaction).filter(
        SalesTransaction.production_cycle_id.in_(
            [first.id, second.id]
        )
    ).delete(synchronize_session=False)
    db.delete(first)
    db.delete(second)
    db.commit()


def apply_production_to_cycle(db, cycle_id, product_id, quantity):
    """
    Put `quantity` units of a product into a cycle's production ledger,
    the way a real apply does - one OptimizationRun plus one
    ProductionApplication.

    Shared by the transaction suites (moved here per Task 10 Step 6)
    because a sale now needs stock to exist before it can be recorded:
    available stock is derived as opening + produced - sold, and
    validation is unconditional once an opening balance is reviewed.

    A plain helper rather than a fixture: callers need to choose the
    cycle, product and quantity per assertion. The rows it writes are
    cleaned up by whichever cycle fixture owns `cycle_id` - both
    transaction_cycle and two_cycles purge their own scope.
    """

    run = OptimizationRun(
        production_cycle_id=cycle_id,
        started_at=datetime(2026, 10, 30, 9, 0),
        status="OPTIMAL",
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    save_production_application(
        db,
        cycle_id,
        run.id,
        {product_id: Decimal(str(quantity))},
        [],
    )
    db.commit()


@pytest.fixture
def transaction_cycle(db):
    """
    A cycle covering late October 2026, so transaction tests can use
    real dates that resolve to a real cycle - required since Task 8's
    resolve_production_cycle_for_date rejects dates outside every
    cycle. Half-open [start, end), so Oct 31 is inside and Nov 1 is
    not.

    FUNCTION-SCOPED deliberately (Amendment C): the stock tests apply
    production into this cycle, and a module- or session-scoped fixture
    holding ledger rows would be wiped by another test's
    function-scoped purge.
    """

    cycle = ProductionCycle(
        cycle_date=datetime(2026, 10, 25),
        start_date=datetime(2026, 10, 25),
        end_date=datetime(2026, 11, 1),
        status="OPEN",
    )

    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    yield cycle

    db.rollback()

    # Scoped ledger purge FIRST (Task 24): these tests apply
    # production into this cycle, and production_applications RESTRICTs
    # both production_cycle_id and optimization_run_id - so neither the
    # cycle nor its runs can be deleted until the applications are
    # gone. Scoped to this cycle, so no other cycle's ledger rows are
    # touched.
    purge_ledger(db, cycle_ids=[cycle.id])

    db.query(SalesTransaction).filter(
        SalesTransaction.production_cycle_id == cycle.id
    ).delete(synchronize_session=False)

    db.query(OptimizationRun).filter(
        OptimizationRun.production_cycle_id == cycle.id
    ).delete(synchronize_session=False)

    db.delete(cycle)
    db.commit()


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
        # Created by the minimum_demand create/update tests in
        # test_products.py, which share one name so this cleanup can
        # reclaim all of them.
        "Test Minimum Demand Product",
    ]

    # Ledger first: production_applications RESTRICTs the test
    # production cycle deleted below, and both ledgers RESTRICT the
    # test products. Scoped to exactly the ids this fixture is about
    # to remove - resolved BEFORE the deletes below, while the rows
    # still exist to resolve.
    purge_ledger(
        db,
        cycle_ids=[
            row[0]
            for row in db.query(ProductionCycle.id)
            .filter(ProductionCycle.cycle_date == datetime(2026, 8, 9))
            .all()
        ],
        product_ids=[
            row[0]
            for row in db.query(Product.id)
            .filter(Product.name.in_(test_product_names))
            .all()
        ],
    )

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
        # No purge here, deliberately: no RESTRICT edge in the schema
        # reaches `resources`. cycle_resources and
        # product_resource_requirements are CASCADE, and
        # production_application_resource_items.resource_id is
        # SET NULL, so deleting a resource can never be blocked by a
        # ledger row. The G1.6 call was for uniformity; under scoped
        # cleanup there is no id for it to pass and a no-scope call
        # now raises by design.
        for resource in resources:
            db.delete(resource)

        db.commit()

@pytest.fixture
def test_products(db, cleanup_test_data):
    products = [
        Product(
            name="Test Dining Table",
            selling_price=Decimal("12500.00"),
            labor_cost=Decimal("0.00"),
            is_active=True,
        ),
        Product(
            name="Test Chair",
            selling_price=Decimal("3500.00"),
            labor_cost=Decimal("0.00"),
            is_active=True,
        ),
        Product(
            name="Test Bed Frame",
            selling_price=Decimal("15000.00"),
            labor_cost=Decimal("0.00"),
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
        # Scoped to these products only: both
        # production_application_items.product_id and
        # opening_inventory_items.product_id are RESTRICT, so the
        # ledger rows referencing them have to go before the products
        # can. Rows about any other product are left alone.
        purge_ledger(
            db,
            product_ids=[product.id for product in products],
        )

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
        # Scoped to this cycle: production_applications RESTRICTs both
        # production_cycle_id and optimization_run_id, and the ORM
        # cascade on ProductionCycle.optimization_runs would otherwise
        # try to delete a run a ledger row still points at.
        purge_ledger(db, cycle_ids=[cycle.id])

        db.query(CycleResource).filter(
            CycleResource.production_cycle_id == cycle.id
        ).delete(
            synchronize_session=False
        )

        db.delete(cycle)
        db.commit()