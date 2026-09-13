"""align existing product master data with thesis requirements

Revision ID: 808a2e897eed
Revises: fa69029d2755
Create Date: 2026-09-13 14:28:17.569224

Data-only migration (no schema change). Updates an EXISTING database's
product master data - already-seeded ProductResourceRequirement
quantities and one Product.labor_cost value - to match the thesis
`req.`/`Furniture cost` sheets, exactly as already verified locally and
in backend/app/database/seed.py (Revision #3 data-alignment work).

Deliberately data-only and narrowly scoped:
- Does NOT touch CycleResource (Sandpaper/Doorknob & Hinge capacity is
  operational per-cycle data, not master data - see the Revision #3
  production-readiness audit).
- Does NOT touch production_allocations, optimization_runs/results,
  forecast_results, or sales_transactions.
- Does NOT create/delete any Product or Resource row - only UPDATEs
  quantity_required on existing product_resource_requirements rows and
  labor_cost on one existing products row, matched by NAME (never by
  id, since this database's actual row ids are unknown and irrelevant).

REQUIREMENT_CHANGES below covers exactly the 47 (product, resource)
pairs whose quantity actually differs between the original seed values
(as committed on main before this work - see backend/app/database/
seed.py at that revision) and the thesis-authoritative figures; a pair
not listed here already matched and is intentionally left untouched.
previous_quantity/previous_labor_cost are used verbatim by downgrade()
and were read directly from that same pre-existing seed.py content,
never invented.

Uses SQLAlchemy Core (op.get_bind().execute(text(...))) rather than
the ORM models, and raises a clear RuntimeError instead of silently
proceeding if an expected product/resource name isn't found - each
UPDATE's rowcount is checked, aborting (and rolling back, since this
runs inside Alembic's single migration transaction) rather than
leaving master data partially or silently unaligned.
"""
from decimal import Decimal
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '808a2e897eed'
down_revision: Union[str, Sequence[str], None] = 'fa69029d2755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (product_name, resource_name, new_quantity, previous_quantity) -
# previous_quantity is the value originally committed in
# backend/app/database/seed.py on main, sourced from git history, not
# invented. Matched by name so this is safe regardless of what ids
# this particular database happens to have assigned.
REQUIREMENT_CHANGES: list[tuple[str, str, str, str]] = [
    # Dining Table (4 seater)
    ("Dining Table (4 seater)", "Wood", "50.0000", "45.0000"),
    ("Dining Table (4 seater)", "Epoxy", "0.6000", "0.3000"),
    ("Dining Table (4 seater)", "Nails", "0.5000", "0.3000"),
    ("Dining Table (4 seater)", "Wood Glue", "0.6000", "0.3000"),
    ("Dining Table (4 seater)", "Sandpaper", "10.0000", "4.0000"),
    ("Dining Table (4 seater)", "Labor", "40.0000", "36.0000"),
    ("Dining Table (4 seater)", "Circular Saw", "15.0000", "3.0000"),
    ("Dining Table (4 seater)", "Hand Planer", "10.0000", "1.0000"),
    ("Dining Table (4 seater)", "Table Planer", "10.0000", "2.0000"),

    # Dining Table (6 seater)
    ("Dining Table (6 seater)", "Wood", "75.0000", "60.0000"),
    ("Dining Table (6 seater)", "Epoxy", "1.0000", "0.4000"),
    ("Dining Table (6 seater)", "Nails", "0.5000", "0.4000"),
    ("Dining Table (6 seater)", "Wood Glue", "1.0000", "0.4000"),
    ("Dining Table (6 seater)", "Sandpaper", "16.0000", "4.0000"),
    ("Dining Table (6 seater)", "Labor", "60.0000", "36.0000"),
    ("Dining Table (6 seater)", "Circular Saw", "20.0000", "3.0000"),
    ("Dining Table (6 seater)", "Hand Planer", "15.0000", "1.0000"),
    ("Dining Table (6 seater)", "Table Planer", "15.0000", "2.0000"),

    # Dining Table (8 seater)
    ("Dining Table (8 seater)", "Wood", "100.0000", "70.0000"),
    ("Dining Table (8 seater)", "Epoxy", "1.5000", "0.5000"),
    ("Dining Table (8 seater)", "Nails", "1.0000", "0.5000"),
    ("Dining Table (8 seater)", "Wood Glue", "1.5000", "0.5000"),
    ("Dining Table (8 seater)", "Sandpaper", "22.0000", "5.0000"),
    ("Dining Table (8 seater)", "Labor", "80.0000", "36.0000"),
    ("Dining Table (8 seater)", "Circular Saw", "30.0000", "3.0000"),
    ("Dining Table (8 seater)", "Hand Planer", "20.0000", "1.0000"),
    ("Dining Table (8 seater)", "Table Planer", "20.0000", "2.0000"),

    # Ordinary Table
    ("Ordinary Table", "Labor", "10.0000", "8.0000"),
    ("Ordinary Table", "Hand Planer", "2.0000", "1.0000"),
    ("Ordinary Table", "Table Planer", "2.0000", "1.0000"),

    # Bed Frame
    ("Bed Frame", "Labor", "40.0000", "24.0000"),
    ("Bed Frame", "Circular Saw", "10.0000", "3.0000"),
    ("Bed Frame", "Hand Planer", "10.0000", "1.0000"),
    ("Bed Frame", "Table Planer", "10.0000", "2.0000"),

    # Door (60x210)
    ("Door (60x210)", "Wood", "25.0000", "22.0000"),
    ("Door (60x210)", "Circular Saw", "2.0000", "1.0000"),
    ("Door (60x210)", "Hand Planer", "3.0000", "0.5000"),

    # Door (70x210)
    ("Door (70x210)", "Circular Saw", "2.0000", "1.0000"),
    ("Door (70x210)", "Hand Planer", "3.0000", "0.5000"),

    # Door (80x210)
    ("Door (80x210)", "Wood", "25.0000", "28.0000"),
    ("Door (80x210)", "Circular Saw", "2.0000", "1.0000"),
    ("Door (80x210)", "Hand Planer", "3.0000", "0.5000"),

    # Door (90x210)
    ("Door (90x210)", "Wood", "25.0000", "30.0000"),
    ("Door (90x210)", "Circular Saw", "2.0000", "1.0000"),
    ("Door (90x210)", "Hand Planer", "3.0000", "0.5000"),

    # High Chair
    ("High Chair", "Hand Planer", "3.0000", "1.0000"),

    # Ordinary Chair
    ("Ordinary Chair", "Hand Planer", "3.0000", "1.0000"),
]

# (product_name, new_labor_cost, previous_labor_cost)
PRODUCT_LABOR_COST_CHANGES: list[tuple[str, str, str]] = [
    ("Dining Table (8 seater)", "10000.00", "7500.00"),
]


def _update_requirement_quantity(
    conn,
    product_name: str,
    resource_name: str,
    quantity: str,
) -> None:
    result = conn.execute(
        text(
            """
            UPDATE product_resource_requirements
            SET quantity_required = :quantity
            FROM products AS p, resources AS r
            WHERE product_resource_requirements.product_id = p.id
              AND product_resource_requirements.resource_id = r.id
              AND p.name = :product_name
              AND r.name = :resource_name
            """
        ),
        {
            "quantity": Decimal(quantity),
            "product_name": product_name,
            "resource_name": resource_name,
        },
    )

    if result.rowcount != 1:
        raise RuntimeError(
            "Expected exactly one product_resource_requirements row for "
            f"product={product_name!r} resource={resource_name!r}, "
            f"found {result.rowcount}. Aborting migration rather than "
            "silently leaving master data inconsistent - this "
            "database's product/resource names don't match what this "
            "migration expects."
        )


def _update_labor_cost(
    conn,
    product_name: str,
    labor_cost: str,
) -> None:
    result = conn.execute(
        text(
            "UPDATE products SET labor_cost = :labor_cost "
            "WHERE name = :name"
        ),
        {
            "labor_cost": Decimal(labor_cost),
            "name": product_name,
        },
    )

    if result.rowcount != 1:
        raise RuntimeError(
            f"Expected exactly one products row for name={product_name!r}, "
            f"found {result.rowcount}. Aborting migration rather than "
            "silently leaving master data inconsistent."
        )


def upgrade() -> None:
    """Upgrade data."""

    conn = op.get_bind()

    for product_name, resource_name, new_quantity, _prev in REQUIREMENT_CHANGES:
        _update_requirement_quantity(
            conn, product_name, resource_name, new_quantity,
        )

    for product_name, new_labor_cost, _prev in PRODUCT_LABOR_COST_CHANGES:
        _update_labor_cost(conn, product_name, new_labor_cost)


def downgrade() -> None:
    """Downgrade data."""

    conn = op.get_bind()

    for product_name, resource_name, _new, previous_quantity in REQUIREMENT_CHANGES:
        _update_requirement_quantity(
            conn, product_name, resource_name, previous_quantity,
        )

    for product_name, _new, previous_labor_cost in PRODUCT_LABOR_COST_CHANGES:
        _update_labor_cost(conn, product_name, previous_labor_cost)
