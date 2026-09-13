"""repair duplicate resource identities and dining table 8 labor cost

Revision ID: 7f3cba51324d
Revises: 808a2e897eed
Create Date: 2026-09-13 15:06:20.087098

Data-only migration (no schema change). Repairs a production data-
consistency issue: resources/services/resource.py::_find_by_normalized_
name() only matches names by case/whitespace-insensitive EXACT string
comparison - it has no typo/alias tolerance. When a soft-deleted
resource was re-added with a slightly different spelling ("Sanpaper"
instead of "Sandpaper", "Table Planner"/"Hand Planner" instead of
"Table Planer"/"Hand Planer", "Doorknob" instead of
"Doorknob & Hinge"), create_resource() never recognized it as the same
resource and created a brand-new row instead of reactivating the
original - leaving product_resource_requirements still pointing at the
now-permanently-inactive original row. Separately, Labor and Circular
Saw appear to have been deactivated with no active replacement ever
created at all.

This migration is deliberately data-only and narrowly scoped:
- Repairs exactly 6 canonical resources: Sandpaper, Doorknob & Hinge,
  Table Planer, Hand Planer, Labor, Circular Saw.
- Does NOT touch Wood, Epoxy, Nails, Wood Glue (no evidence of drift).
- Does NOT touch cycle_resources at all, in either direction. Old,
  now-unreferenced CycleResource rows for a superseded resource id are
  left exactly as they are - they simply stop contributing any
  constraint once no requirement references them (see the accompanying
  investigation report for why that's safe), and this migration must
  never rewrite operational/historical per-cycle data.
- Does NOT touch production_allocations, optimization_runs/results,
  forecast_results, or sales_transactions.
- Does NOT assume any specific resource/product id - every repair is
  re-derived from live data by name at the moment this migration runs
  (see _find_resource_rows below), never from ids observed in any past
  environment.

Repair logic per canonical resource (see _repair_duplicate_resource):
  1. Find every `resources` row whose normalized (lower+trim) name
     matches any of that resource's known aliases (its correct
     spelling plus known typos/variants).
  2. If exactly one is active, that's canonical - remap every OTHER
     (inactive) matching row's product_resource_requirements onto it.
     Refuses (raises) if remapping would collide with
     uq_product_resource_requirement (a product already has a
     requirement row for both the old and the canonical resource) -
     that would be a genuinely ambiguous state needing manual review,
     never silently resolved here.
  3. If zero are active (Labor, Circular Saw), reactivate the single
     inactive match - or, if more than one inactive match exists,
     disambiguate by picking the one actually referenced by a
     requirement row; raises if that's still ambiguous.
  4. Resource.name has a database-level UNIQUE constraint, and the
     original correctly-spelled row is still sitting there (inactive,
     unreferenced after step 2) - so renaming the canonical row to its
     correct spelling would otherwise collide with it. This migration
     detects that and renames the now-orphaned holder out of the way
     first (e.g. "Sandpaper (superseded #<id>)"), then renames the
     canonical row to the clean spelling.
  5. Every step raises a clear RuntimeError (aborting and rolling back
     the whole migration, since Alembic runs a migration in one
     transaction) if an expected canonical record is missing or
     ambiguous - never silently proceeds.

Also fixes products.labor_cost for "Dining Table (8 seater)" to
10000.00, matched by normalized name with a hard requirement of
exactly one match (guards against, and would surface, an unexpected
duplicate Product row rather than silently applying to the wrong one).

Downgrade note (see also the investigation report): the rename + FK
remap for the 4 typo'd resources ARE safely, deterministically
reversible (re-derived the same way upgrade found them - the old,
untouched alias row is still there to remap back onto), so downgrade
reverses those. It deliberately does NOT reverse the Labor/Circular Saw
reactivation or the labor_cost fix: this migration is repairing an
already-drifted, unknown-cause production state (unlike 808a2e897eed,
which reversed to a known, static, git-sourced prior value) - there is
no reliable way to know, at downgrade time, whether those two
resources were genuinely inactive immediately before this migration
ran, or whether labor_cost's prior value was really 0. Silently
guessing either back would risk re-introducing exactly the bug this
migration exists to fix. Leaving them as-is is the safer failure mode.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '7f3cba51324d'
down_revision: Union[str, Sequence[str], None] = '808a2e897eed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (canonical_name, [normalized aliases including the canonical
# spelling itself], revert_name_or_None). revert_name is the single
# typo/variant downgrade renames the canonical row back to; None means
# no rename is ever performed for this resource (Labor/Circular Saw
# have no known typo - only their is_active state was ever in
# question, and that's deliberately not reversed either way).
CANONICAL_RESOURCE_REPAIRS: list[tuple[str, list[str], str | None]] = [
    ("Sandpaper", ["sandpaper", "sanpaper"], "Sanpaper"),
    ("Doorknob & Hinge", ["doorknob & hinge", "doorknob"], "Doorknob"),
    ("Table Planer", ["table planer", "table planner"], "Table Planner"),
    ("Hand Planer", ["hand planer", "hand planner"], "Hand Planner"),
    ("Labor", ["labor"], None),
    ("Circular Saw", ["circular saw"], None),
]

DINING_TABLE_8_NAME = "Dining Table (8 seater)"
DINING_TABLE_8_LABOR_COST = "10000.00"


def _find_resource_rows(conn, aliases: list[str]):
    statement = text(
        "SELECT id, name, is_active FROM resources "
        "WHERE lower(trim(name)) IN :aliases"
    ).bindparams(sa.bindparam("aliases", expanding=True))

    return list(conn.execute(statement, {"aliases": aliases}))


def _is_referenced(conn, resource_id: int) -> bool:
    result = conn.execute(
        text(
            "SELECT 1 FROM product_resource_requirements "
            "WHERE resource_id = :resource_id LIMIT 1"
        ),
        {"resource_id": resource_id},
    )

    return result.first() is not None


def _remap_requirements(conn, from_resource_id: int, to_resource_id: int) -> None:
    if from_resource_id == to_resource_id:
        return

    conflicts = conn.execute(
        text(
            """
            SELECT old_req.product_id
            FROM product_resource_requirements AS old_req
            JOIN product_resource_requirements AS new_req
              ON new_req.product_id = old_req.product_id
             AND new_req.resource_id = :to_resource_id
            WHERE old_req.resource_id = :from_resource_id
            """
        ),
        {"from_resource_id": from_resource_id, "to_resource_id": to_resource_id},
    ).fetchall()

    if conflicts:
        product_ids = [row.product_id for row in conflicts]
        raise RuntimeError(
            f"Cannot remap product_resource_requirements from "
            f"resource_id={from_resource_id} to resource_id={to_resource_id}: "
            f"product(s) {product_ids} already have a requirement row for "
            "both resources, which would violate "
            "uq_product_resource_requirement. Aborting for manual review "
            "rather than silently dropping or corrupting a requirement."
        )

    conn.execute(
        text(
            "UPDATE product_resource_requirements "
            "SET resource_id = :to_resource_id "
            "WHERE resource_id = :from_resource_id"
        ),
        {"to_resource_id": to_resource_id, "from_resource_id": from_resource_id},
    )


def _repair_duplicate_resource(conn, canonical_name: str, aliases: list[str]) -> int:
    rows = _find_resource_rows(conn, aliases)

    if not rows:
        raise RuntimeError(
            f"No resource row found matching any of {aliases!r} for "
            f"canonical resource {canonical_name!r} - cannot repair, "
            "aborting migration rather than creating a new row that "
            "might not match this database's actual history."
        )

    active_rows = [row for row in rows if row.is_active]
    inactive_rows = [row for row in rows if not row.is_active]

    if len(active_rows) > 1:
        raise RuntimeError(
            f"Ambiguous: {len(active_rows)} active resources match "
            f"aliases {aliases!r} for canonical resource "
            f"{canonical_name!r}: {[row.name for row in active_rows]!r}. "
            "Aborting - this needs manual review, not an automatic guess."
        )

    if active_rows:
        canonical_id = active_rows[0].id

        for row in inactive_rows:
            _remap_requirements(conn, row.id, canonical_id)
    else:
        if len(inactive_rows) > 1:
            referenced = [
                row for row in inactive_rows if _is_referenced(conn, row.id)
            ]

            if len(referenced) != 1:
                raise RuntimeError(
                    f"Ambiguous: {len(inactive_rows)} inactive resources "
                    f"match aliases {aliases!r} for canonical resource "
                    f"{canonical_name!r}, and "
                    f"{'none' if not referenced else 'more than one'} of "
                    "them is uniquely referenced by "
                    "product_resource_requirements. Cannot safely "
                    "determine which one to reactivate - aborting for "
                    "manual review."
                )

            canonical_id = referenced[0].id
        else:
            canonical_id = inactive_rows[0].id

        conn.execute(
            text("UPDATE resources SET is_active = true WHERE id = :id"),
            {"id": canonical_id},
        )

    # resources.name is UNIQUE - if a different, now-orphaned row
    # already holds the canonical spelling (the common case: the
    # original row was never misspelled, only its later-created
    # duplicate was), free up that name first. Safe: that row is no
    # longer referenced by any requirement after the remap above.
    holder = conn.execute(
        text(
            "SELECT id FROM resources WHERE name = :name AND id != :canonical_id"
        ),
        {"name": canonical_name, "canonical_id": canonical_id},
    ).first()

    if holder is not None:
        conn.execute(
            text("UPDATE resources SET name = :new_name WHERE id = :id"),
            {
                "new_name": f"{canonical_name} (superseded #{holder.id})",
                "id": holder.id,
            },
        )

    conn.execute(
        text(
            "UPDATE resources SET name = :name "
            "WHERE id = :id AND name != :name"
        ),
        {"name": canonical_name, "id": canonical_id},
    )

    return canonical_id


def _revert_duplicate_resource(
    conn,
    canonical_name: str,
    aliases: list[str],
    revert_name: str | None,
) -> None:
    if revert_name is None:
        # Labor / Circular Saw: no rename was ever performed, and the
        # is_active reactivation is deliberately one-way - see the
        # module docstring. Nothing to revert here.
        return

    # The alias search alone can't find the superseded row anymore:
    # upgrade() renamed it to "<canonical_name> (superseded #<id>)",
    # which no longer normalizes to any alias in `aliases`. Find it by
    # that distinctive rename pattern instead - deterministic, since
    # upgrade() only ever produces names in exactly that shape.
    rows = _find_resource_rows(conn, aliases)
    active_rows = [row for row in rows if row.is_active]

    if len(active_rows) != 1:
        # State doesn't match what upgrade() would have produced -
        # nothing safe/unambiguous to revert.
        return

    canonical_id = active_rows[0].id

    superseded = conn.execute(
        text("SELECT id FROM resources WHERE name LIKE :pattern"),
        {"pattern": f"{canonical_name} (superseded #%)"},
    ).first()

    old_id = superseded.id if superseded is not None else None

    if old_id is not None:
        _remap_requirements(conn, canonical_id, old_id)

    conn.execute(
        text(
            "UPDATE resources SET name = :revert_name "
            "WHERE id = :id AND name = :canonical_name"
        ),
        {
            "revert_name": revert_name,
            "id": canonical_id,
            "canonical_name": canonical_name,
        },
    )

    if old_id is not None:
        conn.execute(
            text("UPDATE resources SET name = :canonical_name WHERE id = :id"),
            {"canonical_name": canonical_name, "id": old_id},
        )


def upgrade() -> None:
    """Upgrade data."""

    conn = op.get_bind()

    for canonical_name, aliases, _revert_name in CANONICAL_RESOURCE_REPAIRS:
        _repair_duplicate_resource(conn, canonical_name, aliases)

    result = conn.execute(
        text(
            "SELECT id FROM products WHERE lower(trim(name)) = :name"
        ),
        {"name": DINING_TABLE_8_NAME.lower()},
    ).fetchall()

    if len(result) != 1:
        raise RuntimeError(
            f"Expected exactly one products row named "
            f"{DINING_TABLE_8_NAME!r}, found {len(result)}. Aborting "
            "migration rather than guessing which row to fix."
        )

    conn.execute(
        text("UPDATE products SET labor_cost = :labor_cost WHERE id = :id"),
        {"labor_cost": DINING_TABLE_8_LABOR_COST, "id": result[0].id},
    )


def downgrade() -> None:
    """Downgrade data."""

    conn = op.get_bind()

    for canonical_name, aliases, revert_name in CANONICAL_RESOURCE_REPAIRS:
        _revert_duplicate_resource(conn, canonical_name, aliases, revert_name)

    # labor_cost is deliberately NOT reverted - see the module
    # docstring's downgrade note.
