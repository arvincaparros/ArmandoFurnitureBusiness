"""
Tests for alembic/versions/7f3cba51324d_repair_duplicate_resource_identities_.py

This migration repairs a production data-consistency issue: a
soft-deleted resource re-added under a slightly different spelling
("Sanpaper" instead of "Sandpaper", etc.) creates a brand-new resource
row instead of reactivating the original, leaving
product_resource_requirements pointing at the now-permanently-inactive
original.

Since this test suite shares the live local dev database (same
pattern as every other test file here) and the REAL canonical
resources ("Sandpaper", "Labor", etc.) already exist there correctly
(single, active, already fixed by an earlier migration) - the
generic repair/revert algorithm is exercised here using safe,
"Repair Test "-prefixed fake resource/product names, never the real
production-mirroring names. A separate smoke test at the bottom calls
the migration's actual upgrade() against the real canonical names to
confirm it is a safe no-op given already-correct data.
"""

import importlib.util
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from app.database.connection import SessionLocal
from app.database.models import Product, ProductResourceRequirement, Resource


def _load_repair_migration():
    spec = importlib.util.spec_from_file_location(
        "repair_migration_7f3cba51324d",
        "alembic/versions/7f3cba51324d_repair_duplicate_resource_identities_.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_repair_migration()

PREFIX = "Repair Test "


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def cleanup_repair_test_data(db):
    def _cleanup():
        db.execute(
            text(
                "DELETE FROM product_resource_requirements "
                "WHERE product_id IN (SELECT id FROM products WHERE name LIKE :p) "
                "   OR resource_id IN (SELECT id FROM resources WHERE name LIKE :p)"
            ),
            {"p": f"{PREFIX}%"},
        )
        db.execute(text("DELETE FROM products WHERE name LIKE :p"), {"p": f"{PREFIX}%"})
        db.execute(text("DELETE FROM resources WHERE name LIKE :p"), {"p": f"{PREFIX}%"})
        db.commit()

    _cleanup()
    yield
    _cleanup()


def _make_resource(db, name, is_active, resource_type="material", unit="pcs"):
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


# --- Remap + rename cases (Sandpaper, Table Planner, Hand Planner, Doorknob) ---


@pytest.mark.parametrize(
    "canonical_name,typo_name",
    [
        (f"{PREFIX}Sandpaper", f"{PREFIX}Sanpaper"),
        (f"{PREFIX}Table Planer", f"{PREFIX}Table Planner"),
        (f"{PREFIX}Hand Planer", f"{PREFIX}Hand Planner"),
        (f"{PREFIX}Doorknob & Hinge", f"{PREFIX}Doorknob"),
    ],
)
def test_repair_remaps_inactive_original_onto_active_typo_and_fixes_spelling(
    db, canonical_name, typo_name,
):
    old_row = _make_resource(db, canonical_name, is_active=False)
    new_row = _make_resource(db, typo_name, is_active=True)
    product = _make_product(db, f"{PREFIX}Product {canonical_name}")
    requirement = _make_requirement(db, product, old_row, Decimal("7.5000"))

    aliases = [canonical_name.lower(), typo_name.lower()]

    conn = db.connection()
    canonical_id = MIGRATION._repair_duplicate_resource(conn, canonical_name, aliases)
    db.commit()

    assert canonical_id == new_row.id

    db.expire_all()
    refreshed_requirement = db.get(ProductResourceRequirement, requirement.id)
    assert refreshed_requirement.resource_id == new_row.id
    assert refreshed_requirement.quantity_required == Decimal("7.5000")
    # Row id/product id preserved - only resource_id changed.
    assert refreshed_requirement.id == requirement.id
    assert refreshed_requirement.product_id == product.id

    refreshed_new = db.get(Resource, new_row.id)
    assert refreshed_new.name == canonical_name
    assert refreshed_new.is_active is True

    refreshed_old = db.get(Resource, old_row.id)
    assert refreshed_old.name == f"{canonical_name} (superseded #{old_row.id})"
    assert refreshed_old.is_active is False


# --- Reactivation case (Labor, Circular Saw style: single row, no active duplicate) ---


def test_repair_reactivates_single_inactive_resource_with_no_duplicate(db):
    name = f"{PREFIX}Labor"
    row = _make_resource(db, name, is_active=False, resource_type="labor", unit="hours")

    conn = db.connection()
    canonical_id = MIGRATION._repair_duplicate_resource(conn, name, [name.lower()])
    db.commit()

    assert canonical_id == row.id

    db.expire_all()
    refreshed = db.get(Resource, row.id)
    assert refreshed.is_active is True
    assert refreshed.name == name  # unchanged - no typo to fix


def test_repair_is_a_noop_when_already_correctly_active(db):
    name = f"{PREFIX}Circular Saw"
    row = _make_resource(db, name, is_active=True)

    conn = db.connection()
    canonical_id = MIGRATION._repair_duplicate_resource(conn, name, [name.lower()])
    db.commit()

    assert canonical_id == row.id
    db.expire_all()
    assert db.get(Resource, row.id).is_active is True


# --- Fail-fast cases ---


def test_repair_raises_when_no_resource_matches(db):
    conn = db.connection()
    with pytest.raises(RuntimeError, match="No resource row found"):
        MIGRATION._repair_duplicate_resource(
            conn, f"{PREFIX}Nonexistent", [f"{PREFIX.lower()}nonexistent"],
        )
    db.rollback()


def test_repair_raises_on_ambiguous_active_duplicates(db):
    name = f"{PREFIX}Circular Saw"
    _make_resource(db, name, is_active=True)
    _make_resource(db, f"{name} dup", is_active=True)

    conn = db.connection()
    with pytest.raises(RuntimeError, match="Ambiguous"):
        MIGRATION._repair_duplicate_resource(
            conn, name, [name.lower(), f"{name} dup".lower()],
        )
    db.rollback()


def test_remap_requirements_refuses_to_violate_unique_constraint(db):
    old_row = _make_resource(db, f"{PREFIX}Sandpaper", is_active=False)
    new_row = _make_resource(db, f"{PREFIX}Sanpaper", is_active=True)
    product = _make_product(db, f"{PREFIX}Conflict Product")

    # Product already has a requirement row for BOTH the old and new
    # resource - remapping would collide with
    # uq_product_resource_requirement.
    _make_requirement(db, product, old_row, Decimal("1.0000"))
    _make_requirement(db, product, new_row, Decimal("2.0000"))

    conn = db.connection()
    with pytest.raises(RuntimeError, match="would violate"):
        MIGRATION._remap_requirements(conn, old_row.id, new_row.id)
    db.rollback()


# --- Idempotency ---


def test_repair_is_idempotent(db):
    canonical_name = f"{PREFIX}Sandpaper"
    typo_name = f"{PREFIX}Sanpaper"
    old_row = _make_resource(db, canonical_name, is_active=False)
    new_row = _make_resource(db, typo_name, is_active=True)
    product = _make_product(db, f"{PREFIX}Idempotent Product")
    requirement = _make_requirement(db, product, old_row, Decimal("3.0000"))

    aliases = [canonical_name.lower(), typo_name.lower()]

    MIGRATION._repair_duplicate_resource(db.connection(), canonical_name, aliases)
    db.commit()

    # Run it again - must not error and must leave the same end state.
    # db.commit() above closed the previous connection - must reacquire.
    MIGRATION._repair_duplicate_resource(db.connection(), canonical_name, aliases)
    db.commit()

    db.expire_all()
    refreshed_requirement = db.get(ProductResourceRequirement, requirement.id)
    assert refreshed_requirement.resource_id == new_row.id
    assert refreshed_requirement.quantity_required == Decimal("3.0000")
    assert db.get(Resource, new_row.id).name == canonical_name
    assert db.get(Resource, old_row.id).name == (
        f"{canonical_name} (superseded #{old_row.id})"
    )


# --- Revert (downgrade) behavior ---


def test_revert_reverses_rename_and_remap(db):
    canonical_name = f"{PREFIX}Table Planer"
    typo_name = f"{PREFIX}Table Planner"
    old_row = _make_resource(db, canonical_name, is_active=False)
    new_row = _make_resource(db, typo_name, is_active=True)
    product = _make_product(db, f"{PREFIX}Revert Product")
    requirement = _make_requirement(db, product, old_row, Decimal("4.2500"))

    aliases = [canonical_name.lower(), typo_name.lower()]

    MIGRATION._repair_duplicate_resource(db.connection(), canonical_name, aliases)
    db.commit()

    # db.commit() above closed the previous connection - must reacquire.
    MIGRATION._revert_duplicate_resource(
        db.connection(), canonical_name, aliases, typo_name,
    )
    db.commit()

    db.expire_all()
    refreshed_requirement = db.get(ProductResourceRequirement, requirement.id)
    assert refreshed_requirement.resource_id == old_row.id
    assert refreshed_requirement.quantity_required == Decimal("4.2500")

    refreshed_old = db.get(Resource, old_row.id)
    assert refreshed_old.name == canonical_name
    assert refreshed_old.is_active is False  # never touched by repair/revert

    refreshed_new = db.get(Resource, new_row.id)
    assert refreshed_new.name == typo_name
    assert refreshed_new.is_active is True  # never touched by repair/revert


def test_revert_does_nothing_for_none_revert_name(db):
    """Labor/Circular Saw style: revert_name=None means the reactivation
    is one-way and revert() must not touch is_active in either direction."""

    name = f"{PREFIX}Labor"
    row = _make_resource(db, name, is_active=False)

    MIGRATION._repair_duplicate_resource(db.connection(), name, [name.lower()])
    db.commit()

    db.expire_all()
    assert db.get(Resource, row.id).is_active is True

    # db.commit() above closed the previous connection - must reacquire.
    MIGRATION._revert_duplicate_resource(
        db.connection(), name, [name.lower()], None,
    )
    db.commit()

    db.expire_all()
    # Still active - revert_name=None means "don't touch is_active".
    assert db.get(Resource, row.id).is_active is True


# --- Real canonical resources: smoke test against actual live data ---


def test_real_canonical_resources_upgrade_is_a_safe_noop(db):
    """
    The 6 real canonical resources in this dev DB are already correctly
    active/named/singular (already fixed by earlier migration work) -
    so running the actual upgrade() logic against them must be a
    genuine no-op: no errors, no changes. This is the closest this
    suite gets to exercising the real CANONICAL_RESOURCE_REPAIRS/
    DINING_TABLE_8_NAME constants without risking real data.
    """

    before = {
        r.name: (r.id, r.is_active)
        for r in db.scalars(
            select(Resource).where(
                Resource.name.in_(
                    [
                        "Wood", "Epoxy", "Nails", "Wood Glue", "Sandpaper",
                        "Doorknob & Hinge", "Labor", "Circular Saw",
                        "Table Planer", "Hand Planer",
                    ]
                )
            )
        ).all()
    }

    dining8_before = db.scalars(
        select(Product).where(Product.name == "Dining Table (8 seater)")
    ).first()

    conn = db.connection()

    for canonical_name, aliases, _revert_name in MIGRATION.CANONICAL_RESOURCE_REPAIRS:
        MIGRATION._repair_duplicate_resource(conn, canonical_name, aliases)

    result = conn.execute(
        text("SELECT id FROM products WHERE lower(trim(name)) = :name"),
        {"name": MIGRATION.DINING_TABLE_8_NAME.lower()},
    ).fetchall()
    assert len(result) == 1
    conn.execute(
        text("UPDATE products SET labor_cost = :v WHERE id = :id"),
        {"v": MIGRATION.DINING_TABLE_8_LABOR_COST, "id": result[0].id},
    )
    db.commit()

    db.expire_all()
    after = {
        r.name: (r.id, r.is_active)
        for r in db.scalars(
            select(Resource).where(Resource.name.in_(before.keys()))
        ).all()
    }
    assert before == after  # nothing changed - genuine no-op

    dining8_after = db.get(Product, dining8_before.id)
    assert dining8_after.labor_cost == Decimal("10000.00")
