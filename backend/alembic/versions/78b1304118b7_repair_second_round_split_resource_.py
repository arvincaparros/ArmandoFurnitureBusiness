"""repair second-round split resource identities and add normalized unique index

Revision ID: 78b1304118b7
Revises: 7f3cba51324d
Create Date: 2026-10-07 13:37:28.519730

Data + schema migration. Repairs a RECURRENCE of the exact bug
`7f3cba51324d` already fixed once (2026-09-13): a resource soft-deleted
via DELETE /api/resources/{id} (is_active=false, row kept) and then
re-added through POST /api/resources with a name that normalizes
(lower+trim) to the same string but isn't byte-identical - this time
purely a case difference ("Circular saw" vs "Circular Saw"), not a
misspelling - ends up as a brand-new row instead of reactivating the
original. The UAT screenshot this migration was written for shows
exactly this for Circular Saw: an inactive "Circular Saw" row still
holding every real ProductResourceRequirement, next to an active
"Circular saw" row holding none.

`_find_by_normalized_name()` in app/services/resource.py (added in
6e25d3e, well before this incident) already does a case/whitespace-
insensitive lookup and already reactivates the original row when it
finds one - in isolation that logic is correct for this exact case.
What it cannot defend against on its own is a race: two concurrent
POST /api/resources requests for case-variant names both run their
SELECT before either has committed its INSERT, both see "no existing
match", and both successfully commit a new row, because the table's
only earlier backstop (`UniqueConstraint("name")`) is an EXACT-string
constraint that two differently-cased strings never trip. That is the
most likely mechanism behind the live duplicate this migration repairs
(see the accompanying investigation write-up) - and it is exactly what
part 3 of this change (a normalized unique index, see below) closes at
the database level, which an application-level SELECT-then-act check
never fully can.

Migration order matters and is enforced in upgrade():
  1. Repair the five known resource families below (remap any stale
     inactive row's product_resource_requirements onto the active
     canonical row, rename the stale row out of the way).
  2. Verify, across the ENTIRE resources table (not just the five known
     families), that no two rows still normalize to the same
     lower(trim(name)) - abort rather than create an index that would
     immediately be violated by something this migration didn't know
     to look for.
  3. Only then create the unique index on lower(trim(name)).

Repair approach - deliberately NOT a blind id-to-id remap:
  Identification is by CURRENT name/state shape (exactly one active row
  normalizing to the canonical name is the row every requirement should
  end up on; any OTHER row normalizing to it is stale), reusing the
  exact same `_repair_duplicate_resource`/`_remap_requirements` logic
  `7f3cba51324d` already proved - duplicated here rather than imported,
  so this migration stays self-contained if that file is ever archived.
  This intentionally does NOT hardcode the specific numeric ids
  observed on the live site (Circular Saw 8/11, Sandpaper 5/20,
  Doorknob & Hinge 6/23, Table Planer 9/21, Hand Planer 10/22) as a
  precondition, because this same migration file also runs against
  every other environment (local dev, CI, a fresh seed) where those
  numeric ids don't exist at all - a hardcoded-id check would either be
  meaningless noise there or, worse, tempt a future edit to "fix" it
  for a new environment and silently weaken the real safety property.
  The actual safety property enforced is structural: at most one ACTIVE
  row may normalize to a given canonical name (raises immediately if
  not, matching `7f3cba51324d`'s own ambiguity handling verbatim), and
  the post-repair, whole-table scan in step 2 above is what catches
  anything an id-based assumption could have missed. Known-production
  ids are not needed as a precondition for that to be safe - they were
  the investigation's evidence that these five specific names need
  checking, not something the repair logic has to trust.
  For four of the five families (Sandpaper, Doorknob & Hinge, Table
  Planer, Hand Planer) both environments inspected (production via its
  API, local dev via direct query) already show a single clean active
  row - only Circular Saw currently has a live split. Running the
  repair for all five anyway is what makes this a true no-op rather
  than a lucky skip on an environment where nothing is currently wrong.

Explicitly out of scope (same as `7f3cba51324d`, and per the
accompanying investigation's explicit request):
  - CycleResource is never touched in either direction. A stale row's
    CycleResource entries become unreferenced the same way
    `7f3cba51324d` already accepted as safe (they stop contributing any
    constraint once no requirement references their resource_id).
  - ProductionAllocation, ResourceUtilizationHistory, and
    OptimizationResult/-History are never touched.
  - No Resource row is ever deleted. No ProductResourceRequirement row
    ID is ever created or deleted - only `resource_id` is updated on
    the existing row, exactly as `7f3cba51324d` already does.
  - requirement quantities are never modified.

Downgrade: the unique index is always dropped first (a prerequisite
for any rename that could recreate a normalized duplicate). Only the
Circular Saw repair is reversed - it is the one family this migration
actually confirmed changes something on the known-affected environment,
so it is the only one with a known, trustworthy prior state to restore.
The other four are expected no-ops on every environment inspected so
far; IF a future environment's upgrade() genuinely repairs one of them
too (i.e. a real split existed there that wasn't visible from the
investigation this migration is based on), downgrade will NOT reverse
that specific repair. Guessing a revert for a drift this migration
never confirmed existing would risk renaming/remapping a row that was
never actually touched - the unsafe direction - so, per the standing
instruction to document rather than implement an unsafe downgrade, this
is a deliberate, documented limitation, not an oversight.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '78b1304118b7'
down_revision: Union[str, Sequence[str], None] = '7f3cba51324d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NORMALIZED_NAME_INDEX = "ix_resources_normalized_name"

# (canonical_name, revert_name_or_None) - revert_name is the exact
# pre-upgrade active-row spelling to restore on downgrade; None means
# "this family is an expected no-op everywhere inspected - don't guess
# a revert for it" (see the module docstring's Downgrade section).
SECOND_ROUND_RESOURCE_REPAIRS: list[tuple[str, str | None]] = [
    ("Circular Saw", "Circular saw"),
    ("Sandpaper", None),
    ("Doorknob & Hinge", None),
    ("Table Planer", None),
    ("Hand Planer", None),
]


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
        return

    rows = _find_resource_rows(conn, aliases)
    active_rows = [row for row in rows if row.is_active]

    if len(active_rows) != 1:
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


def _assert_no_normalized_duplicates(conn) -> None:
    """
    Whole-table safety net, not limited to the five known families -
    this is what lets step 1's repair stay narrowly scoped to known
    evidence while still making the index creation in step 3 safe
    against anything that evidence didn't cover. Raises (aborting the
    whole migration) rather than ever creating an index that would
    immediately conflict with data it didn't know to fix.
    """

    duplicates = conn.execute(
        text(
            """
            SELECT lower(trim(name)) AS normalized,
                   array_agg(id ORDER BY id) AS ids,
                   array_agg(name ORDER BY id) AS names
            FROM resources
            GROUP BY lower(trim(name))
            HAVING count(*) > 1
            """
        )
    ).fetchall()

    if duplicates:
        details = [
            f"{row.normalized!r} -> ids={list(row.ids)} names={list(row.names)}"
            for row in duplicates
        ]
        raise RuntimeError(
            "Refusing to create the normalized unique index: "
            f"{len(duplicates)} normalized-name duplicate group(s) still "
            f"exist after repair: {details}. Aborting migration for "
            "manual review rather than creating an index that would "
            "immediately be unsatisfiable."
        )


def upgrade() -> None:
    """Upgrade schema and data."""

    conn = op.get_bind()

    # Step 1: repair the five known families (see module docstring -
    # no typo aliases needed this round, the drift is case/whitespace
    # only, already covered by lower(trim(...))).
    for canonical_name, _revert_name in SECOND_ROUND_RESOURCE_REPAIRS:
        _repair_duplicate_resource(conn, canonical_name, [canonical_name.lower()])

    # Step 2: whole-table verification - fail fast rather than create
    # an index that would immediately be violated by something the
    # five known families didn't cover.
    _assert_no_normalized_duplicates(conn)

    # Step 3: the actual, permanent guarantee. Backs
    # _find_by_normalized_name()'s application-level check with a real
    # database constraint, closing the race where two concurrent
    # case/whitespace-variant creates both pass that check before
    # either commits (see app/services/resource.py::create_resource -
    # its IntegrityError handling already converts a violation of this
    # index into the existing 409 duplicate-resource response).
    op.execute(
        text(
            f"CREATE UNIQUE INDEX {NORMALIZED_NAME_INDEX} "
            "ON resources (lower(trim(name)))"
        )
    )


def downgrade() -> None:
    """Downgrade schema and data."""

    conn = op.get_bind()

    # Index first - a revert below renames a row back to a spelling
    # that would otherwise collide with the index while a second row
    # still holds the canonical name.
    op.execute(text(f"DROP INDEX IF EXISTS {NORMALIZED_NAME_INDEX}"))

    for canonical_name, revert_name in SECOND_ROUND_RESOURCE_REPAIRS:
        _revert_duplicate_resource(
            conn, canonical_name, [canonical_name.lower()], revert_name,
        )
