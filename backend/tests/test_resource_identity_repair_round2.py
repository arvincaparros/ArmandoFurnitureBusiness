"""
Tests for alembic/versions/78b1304118b7_repair_second_round_split_resource_.py
and the create_resource() race it closes.

Same safety convention as test_resource_identity_repair.py: this suite
shares the live local dev database, so every fixture here uses a
"Repair Round2 Test "-prefixed name, never the real canonical resource
names. The one exception is the final smoke test, which runs the real
migration helpers against the real canonical names to confirm they are
a safe no-op given this dev database's already-clean state.
"""

import importlib.util
import threading
import time
from contextlib import contextmanager
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Product, ProductResourceRequirement, Resource
from app.schemas.resource import ResourceCreate
from app.services import resource as resource_service
from app.services.resource import DUPLICATE_NAME_ERROR, create_resource


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "repair_migration_78b1304118b7",
        "alembic/versions/78b1304118b7_repair_second_round_split_resource_.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration()

PREFIX = "Repair Round2 Test "

INDEX_NAME = MIGRATION.NORMALIZED_NAME_INDEX


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _index_exists(db: Session) -> bool:
    result = db.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": INDEX_NAME},
    )
    return result.first() is not None


@pytest.fixture(autouse=True)
def cleanup_round2_test_data(db):
    def _cleanup():
        # ILIKE, not LIKE: several tests below deliberately insert
        # case-variant spellings of the prefix itself (that's the
        # whole point of the case/whitespace-duplicate scenarios being
        # tested) - a case-sensitive LIKE would leave a lowercased
        # leftover row behind for every later test run to trip over.
        db.execute(
            text(
                "DELETE FROM product_resource_requirements "
                "WHERE product_id IN (SELECT id FROM products WHERE name ILIKE :p) "
                "   OR resource_id IN (SELECT id FROM resources WHERE name ILIKE :p)"
            ),
            {"p": f"{PREFIX}%"},
        )
        db.execute(text("DELETE FROM products WHERE name ILIKE :p"), {"p": f"{PREFIX}%"})
        db.execute(text("DELETE FROM resources WHERE name ILIKE :p"), {"p": f"{PREFIX}%"})
        db.commit()

    _cleanup()
    yield
    _cleanup()


@contextmanager
def _without_normalized_index(db):
    """
    Several tests below need to recreate the EXACT pre-migration
    scenario this migration repairs: two resource rows that already
    normalize to the same lower(trim(name)). On this dev DB, migration
    78b1304118b7 has already run and that index now exists, so such an
    insert is no longer physically possible - which is itself the
    correct, intended behavior going forward, not a problem to work
    around in production. For these specific tests only, drop the
    index, build the fixture, run the assertion, then always recreate
    it - mirroring the real migration's own actual order of operations
    (repair runs BEFORE the index exists), never leaving the index
    missing once the test is done.
    """

    db.commit()
    db.execute(text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
    db.commit()

    try:
        yield
    finally:
        db.commit()
        db.execute(
            text(
                f"CREATE UNIQUE INDEX {INDEX_NAME} "
                "ON resources (lower(trim(name)))"
            )
        )
        db.commit()


def _make_resource(db, name, is_active=True, resource_type="machine", unit="hrs"):
    resource = Resource(name=name, resource_type=resource_type, unit=unit, is_active=is_active)
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


def _make_product(db, name):
    product = Product(name=name, selling_price=Decimal("100.00"), labor_cost=Decimal("0.00"))
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def _make_requirement(db, product, resource, quantity):
    requirement = ProductResourceRequirement(
        product_id=product.id, resource_id=resource.id, quantity_required=quantity,
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


# --- Repairs all five known families, reproducing the exact live shape:
# a case-variant (not typo'd) active duplicate next to the inactive
# original holding every real requirement. ---


@pytest.mark.parametrize(
    "canonical_name,case_variant_name",
    [
        (f"{PREFIX}Circular Saw", f"{PREFIX}Circular saw"),
        (f"{PREFIX}Sandpaper", f"{PREFIX}sandpaper"),
        (f"{PREFIX}Doorknob & Hinge", f"{PREFIX}doorknob & hinge"),
        (f"{PREFIX}Table Planer", f"{PREFIX}table planer"),
        (f"{PREFIX}Hand Planer", f"{PREFIX}HAND PLANER"),
    ],
)
def test_repair_remaps_inactive_original_onto_active_case_variant(
    db, canonical_name, case_variant_name,
):
    with _without_normalized_index(db):
        old_row = _make_resource(db, canonical_name, is_active=False)
        new_row = _make_resource(db, case_variant_name, is_active=True)
        product = _make_product(db, f"{PREFIX}Product {canonical_name}")
        requirement = _make_requirement(db, product, old_row, Decimal("12.5000"))

        # Repair resolves the duplicate before the index is recreated
        # on exit - exactly the real migration's own step ordering.
        canonical_id = MIGRATION._repair_duplicate_resource(
            db.connection(), canonical_name, [canonical_name.lower()],
        )
        db.commit()

    assert canonical_id == new_row.id

    db.expire_all()

    # Requirement row ID and quantity survive untouched - only
    # resource_id is remapped.
    refreshed_requirement = db.get(ProductResourceRequirement, requirement.id)
    assert refreshed_requirement.id == requirement.id
    assert refreshed_requirement.product_id == product.id
    assert refreshed_requirement.resource_id == new_row.id
    assert refreshed_requirement.quantity_required == Decimal("12.5000")

    refreshed_new = db.get(Resource, new_row.id)
    assert refreshed_new.name == canonical_name
    assert refreshed_new.is_active is True

    refreshed_old = db.get(Resource, old_row.id)
    assert refreshed_old.name == f"{canonical_name} (superseded #{old_row.id})"
    assert refreshed_old.is_active is False

    # No normalized duplicate remains for this name.
    MIGRATION._assert_no_normalized_duplicates(db.connection())


def test_repair_is_a_noop_when_family_already_clean(db):
    """
    Four of the five known families are already a single clean active
    row on this dev DB (confirmed by investigation) - repair must be a
    genuine no-op for that shape, not an error.
    """

    name = f"{PREFIX}Already Clean Resource"
    row = _make_resource(db, name, is_active=True)

    conn = db.connection()
    canonical_id = MIGRATION._repair_duplicate_resource(conn, name, [name.lower()])
    db.commit()

    assert canonical_id == row.id
    db.expire_all()
    refreshed = db.get(Resource, row.id)
    assert refreshed.name == name
    assert refreshed.is_active is True


# --- Fail-fast / ambiguity ---


def test_repair_raises_on_ambiguous_active_duplicates(db):
    name = f"{PREFIX}Ambiguous Saw"
    _make_resource(db, name, is_active=True)
    _make_resource(db, f"{name} v2", is_active=True)

    conn = db.connection()
    with pytest.raises(RuntimeError, match="Ambiguous"):
        MIGRATION._repair_duplicate_resource(
            conn, name, [name.lower(), f"{name} v2".lower()],
        )
    db.rollback()


def test_repair_raises_when_remap_would_violate_unique_requirement_constraint(db):
    with _without_normalized_index(db):
        old_row = _make_resource(db, f"{PREFIX}Conflict Old", is_active=False)
        new_row = _make_resource(db, f"{PREFIX}conflict old", is_active=True)
        product = _make_product(db, f"{PREFIX}Conflict Product")

        _make_requirement(db, product, old_row, Decimal("1.0000"))
        _make_requirement(db, product, new_row, Decimal("2.0000"))

        with pytest.raises(RuntimeError, match="would violate"):
            MIGRATION._repair_duplicate_resource(
                db.connection(), f"{PREFIX}Conflict Old", [f"{PREFIX}conflict old".lower()],
            )
        db.rollback()

        # Repair correctly refused to touch anything - the duplicate
        # this test deliberately created is still here. Clean it up
        # ourselves (same rows the autouse fixture would remove at
        # teardown anyway) so the index can be safely recreated below;
        # this is test-fixture cleanup, not part of the behavior under
        # test.
        db.execute(
            text(
                "DELETE FROM product_resource_requirements "
                "WHERE product_id = :pid"
            ),
            {"pid": product.id},
        )
        db.execute(text("DELETE FROM resources WHERE id = :id"), {"id": new_row.id})
        db.commit()


def test_assert_no_normalized_duplicates_raises_when_duplicates_remain(db):
    with _without_normalized_index(db):
        name = f"{PREFIX}Unrepaired"
        _make_resource(db, name, is_active=True)
        second = _make_resource(db, f"  {name.upper()}  ", is_active=False)

        with pytest.raises(RuntimeError, match="normalized-name duplicate"):
            MIGRATION._assert_no_normalized_duplicates(db.connection())
        db.rollback()

        # Same rationale as above - clean up this test's own
        # deliberately-duplicate fixture before the index is recreated.
        db.execute(text("DELETE FROM resources WHERE id = :id"), {"id": second.id})
        db.commit()


def test_assert_no_normalized_duplicates_passes_when_clean(db):
    conn = db.connection()
    # Must not raise against this dev DB's actual current state.
    MIGRATION._assert_no_normalized_duplicates(conn)


# --- Downgrade ---


def test_revert_reverses_circular_saw_style_repair(db):
    """
    A full revert deliberately recreates the pre-migration duplicate
    (that's the whole point of downgrade) - which is, by definition,
    incompatible with the normalized unique index coexisting at the
    same time. The real migration's downgrade() drops the index BEFORE
    reverting for exactly this reason; this test mirrors that same
    ordering by hand, then cleans up its own fixture and restores the
    index itself rather than leaving a duplicate sitting on a shared
    dev database.
    """

    canonical_name = f"{PREFIX}Circular Saw"
    case_variant_name = f"{PREFIX}Circular saw"

    with _without_normalized_index(db):
        old_row = _make_resource(db, canonical_name, is_active=False)
        new_row = _make_resource(db, case_variant_name, is_active=True)
        product = _make_product(db, f"{PREFIX}Revert Product")
        requirement = _make_requirement(db, product, old_row, Decimal("9.0000"))

        MIGRATION._repair_duplicate_resource(
            db.connection(), canonical_name, [canonical_name.lower()],
        )
        db.commit()

        MIGRATION._revert_duplicate_resource(
            db.connection(), canonical_name, [canonical_name.lower()], case_variant_name,
        )
        db.commit()

        db.expire_all()
        refreshed_requirement = db.get(ProductResourceRequirement, requirement.id)
        assert refreshed_requirement.resource_id == old_row.id
        assert refreshed_requirement.quantity_required == Decimal("9.0000")

        assert db.get(Resource, old_row.id).name == canonical_name
        assert db.get(Resource, old_row.id).is_active is False
        assert db.get(Resource, new_row.id).name == case_variant_name
        assert db.get(Resource, new_row.id).is_active is True

        # Test-fixture cleanup (the duplicate restored above is the
        # expected, correct output of revert - not something left
        # over by accident) so the index can be safely recreated on
        # exit from this context.
        db.execute(
            text(
                "DELETE FROM product_resource_requirements WHERE product_id = :pid"
            ),
            {"pid": product.id},
        )
        db.execute(
            text("DELETE FROM resources WHERE id IN (:a, :b)"),
            {"a": old_row.id, "b": new_row.id},
        )
        db.commit()


def test_revert_does_nothing_for_none_revert_name(db):
    name = f"{PREFIX}No Revert Family"
    row = _make_resource(db, name, is_active=True)

    # Nothing to repair (already clean) - revert must still be a no-op.
    MIGRATION._repair_duplicate_resource(db.connection(), name, [name.lower()])
    db.commit()

    MIGRATION._revert_duplicate_resource(db.connection(), name, [name.lower()], None)
    db.commit()

    db.expire_all()
    refreshed = db.get(Resource, row.id)
    assert refreshed.name == name
    assert refreshed.is_active is True


# --- The real canonical names: safe-no-op smoke test ---


def test_real_canonical_families_upgrade_helpers_are_a_safe_noop(db):
    """
    All five real canonical resources are, on this dev DB, already a
    single clean active row each (verified by direct investigation) -
    running the actual repair helper against the real names must not
    change or error on anything.
    """

    names = [
        "Circular Saw", "Sandpaper", "Doorknob & Hinge",
        "Table Planer", "Hand Planer",
    ]

    before = {
        r.name: (r.id, r.is_active)
        for r in db.scalars(select(Resource).where(Resource.name.in_(names))).all()
    }

    conn = db.connection()
    for canonical_name, _revert_name in MIGRATION.SECOND_ROUND_RESOURCE_REPAIRS:
        MIGRATION._repair_duplicate_resource(conn, canonical_name, [canonical_name.lower()])

    MIGRATION._assert_no_normalized_duplicates(conn)
    db.commit()

    db.expire_all()
    after = {
        r.name: (r.id, r.is_active)
        for r in db.scalars(select(Resource).where(Resource.name.in_(names))).all()
    }
    assert before == after


# --- The normalized unique index itself (requires `alembic upgrade head`
# to have actually been run against this dev DB - see the migration
# simulation report; skipped rather than failed if it hasn't). ---


def _require_index(db):
    if not _index_exists(db):
        pytest.skip(
            f"{INDEX_NAME} does not exist on this database yet - "
            "run `alembic upgrade head` first."
        )


def test_direct_insert_of_case_variant_duplicate_rejected_by_index(db):
    _require_index(db)

    _make_resource(db, f"{PREFIX}Index Circular Saw")

    try:
        with pytest.raises(Exception):
            db.execute(
                text(
                    "INSERT INTO resources (name, resource_type, unit, is_active) "
                    "VALUES (:name, 'machine', 'hrs', true)"
                ),
                {"name": f"{PREFIX}index circular saw"},
            )
            db.commit()
    finally:
        db.rollback()


def test_direct_insert_of_whitespace_variant_duplicate_rejected_by_index(db):
    _require_index(db)

    _make_resource(db, f"{PREFIX}Index Table Saw")

    try:
        with pytest.raises(Exception):
            db.execute(
                text(
                    "INSERT INTO resources (name, resource_type, unit, is_active) "
                    "VALUES (:name, 'machine', 'hrs', true)"
                ),
                {"name": f"  {PREFIX}Index Table Saw  "},
            )
            db.commit()
    finally:
        db.rollback()


def test_create_resource_concurrent_case_variant_insert_resolves_without_duplicate(
    db,
):
    """
    Simulates the exact race believed to have produced the live
    Circular Saw split: two concurrent POST /api/resources requests for
    case-variant names, both reaching _find_by_normalized_name before
    either has committed. Requires the normalized unique index (see
    migration 78b1304118b7) to be the thing that actually prevents two
    rows from surviving.
    """

    _require_index(db)

    base_name = f"{PREFIX}Race Circular Saw"
    original_find = resource_service._find_by_normalized_name
    barrier = threading.Barrier(2)

    def synchronized_find(session, name, exclude_id=None):
        result = original_find(session, name, exclude_id)
        barrier.wait(timeout=5)
        time.sleep(0.2)
        return result

    results: dict[str, Resource] = {}
    errors: dict[str, Exception] = {}

    def worker(key: str, name: str):
        session = SessionLocal()
        try:
            data = ResourceCreate(name=name, resource_type="machine", unit="hrs")
            results[key] = create_resource(session, data)
        except Exception as exc:  # noqa: BLE001 - captured for assertion below
            errors[key] = exc
        finally:
            session.close()

    try:
        resource_service._find_by_normalized_name = synchronized_find

        t1 = threading.Thread(target=worker, args=("a", base_name))
        t2 = threading.Thread(target=worker, args=("b", base_name.lower()))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
    finally:
        resource_service._find_by_normalized_name = original_find

    assert len(results) + len(errors) == 2

    # The database row count is the actual property under test - two
    # concurrent creates for case-variant names must never leave two
    # rows behind. In-thread result/error bookkeeping is useful for
    # diagnosis but is a softer signal: under a loaded test run, a
    # thread's post-commit db.refresh() can occasionally surface a
    # late connection hiccup as an exception even though its INSERT
    # already committed - that is noise in this test's harness, not a
    # violation of the guarantee the index itself provides.
    rows = db.scalars(
        select(Resource).where(
            func.lower(func.trim(Resource.name)) == base_name.lower()
        )
    ).all()
    assert len(rows) == 1, (
        f"race produced {len(rows)} resource row(s) for the same "
        "normalized name instead of exactly one"
    )

    for exc in errors.values():
        assert isinstance(exc, ValueError), (
            f"expected a clean duplicate-name ValueError, got {exc!r}"
        )
        assert str(exc) == DUPLICATE_NAME_ERROR
