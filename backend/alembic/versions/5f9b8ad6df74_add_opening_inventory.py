"""add opening inventory

Adds the opening_inventory_sets / opening_inventory_items pair that
holds the auditable declaration of finished-goods stock on hand at
the moment the production ledger starts tracking. A header/items
design (not a flat table) because the review step is what gates
stock-based sales validation, and a review needs something to attach
a status/reviewer/timestamp to.

A partial unique index enforces at most one REVIEWED set at a time -
DRAFT and SUPERSEDED rows may repeat freely, but only one row may ever
carry status = 'REVIEWED', because every derived stock figure in the
system depends on there being exactly one authoritative opening
balance.

Revision ID: 5f9b8ad6df74
Revises: c7a1e4d9f2b8
Create Date: 2026-10-30 18:56:36.836186

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f9b8ad6df74'
down_revision: Union[str, Sequence[str], None] = 'c7a1e4d9f2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "opening_inventory_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("set_number", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("effective_date", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_opening_inventory_sets_id"),
        "opening_inventory_sets",
        ["id"],
    )

    op.create_index(
        op.f("ix_opening_inventory_sets_set_number"),
        "opening_inventory_sets",
        ["set_number"],
        unique=True,
    )

    op.create_index(
        op.f("ix_opening_inventory_sets_status"),
        "opening_inventory_sets",
        ["status"],
    )

    # Partial unique index: at most ONE reviewed set may exist at a
    # time. Not expressible as a plain UniqueConstraint - DRAFT and
    # SUPERSEDED rows must be allowed to repeat freely.
    op.create_index(
        "uq_opening_inventory_single_reviewed",
        "opening_inventory_sets",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'REVIEWED'"),
    )

    op.create_table(
        "opening_inventory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "opening_inventory_set_id", sa.Integer(), nullable=False,
        ),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["opening_inventory_set_id"],
            ["opening_inventory_sets.id"],
            ondelete="CASCADE",
        ),
        # RESTRICT: a reviewed opening balance is history that must
        # outlive the product it was declared against - see
        # OpeningInventoryItem.product_id in app/database/models.py.
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "opening_inventory_set_id",
            "product_id",
            name="uq_opening_inventory_item",
        ),
    )

    op.create_index(
        op.f("ix_opening_inventory_items_id"),
        "opening_inventory_items",
        ["id"],
    )

    op.create_index(
        op.f("ix_opening_inventory_items_opening_inventory_set_id"),
        "opening_inventory_items",
        ["opening_inventory_set_id"],
    )

    op.create_index(
        op.f("ix_opening_inventory_items_product_id"),
        "opening_inventory_items",
        ["product_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("opening_inventory_items")
    op.drop_index(
        "uq_opening_inventory_single_reviewed",
        table_name="opening_inventory_sets",
    )
    op.drop_table("opening_inventory_sets")
