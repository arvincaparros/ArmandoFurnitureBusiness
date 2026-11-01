"""add production cycle to sales transactions

Revision ID: 9733160b3d9a
Revises: 93076b221d5d
Create Date: 2026-10-31 21:10:20.863728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9733160b3d9a'
down_revision: Union[str, Sequence[str], None] = '93076b221d5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable with NO backfill on purpose: a pre-existing row has no
    # reliable production cycle, and guessing one would put invented
    # numbers into a real cycle's reported sales. Such rows still count
    # toward all-time sold (and therefore available stock) - only the
    # per-cycle breakdown excludes them.
    op.add_column(
        "sales_transactions",
        sa.Column("production_cycle_id", sa.Integer(), nullable=True),
    )

    op.create_index(
        op.f("ix_sales_transactions_production_cycle_id"),
        "sales_transactions",
        ["production_cycle_id"],
    )

    op.create_foreign_key(
        "fk_sales_transactions_production_cycle_id",
        "sales_transactions",
        "production_cycles",
        ["production_cycle_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_sales_transactions_production_cycle_id",
        "sales_transactions",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_sales_transactions_production_cycle_id"),
        table_name="sales_transactions",
    )
    op.drop_column("sales_transactions", "production_cycle_id")
