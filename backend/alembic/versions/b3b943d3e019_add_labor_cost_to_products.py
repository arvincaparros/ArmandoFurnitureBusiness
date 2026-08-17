"""add labor cost to products

Revision ID: b3b943d3e019
Revises: 4da4bef9b8a4
Create Date: 2026-08-17 09:39:55.591331

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3b943d3e019'
down_revision: Union[str, Sequence[str], None] = '4da4bef9b8a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Client reconciliation finding: the client's spreadsheet uses a
    # per-product labor cost that does not reduce to labor_hours x a
    # shared rate (proven via products with identical labor hours/BOM
    # but different total cost). Labor HOURS stay exactly as they are
    # today (still a ProductResourceRequirement row against the
    # "Labor" Resource, still constraining capacity in the optimizer)
    # - this column is only the per-product labor COST used instead of
    # labor_hours x CycleResource(Labor).unit_price.
    #
    # Added nullable first, backfilled to 0 for existing rows, then
    # locked to NOT NULL - same safe pattern already used by
    # a28aae90b202 for users.email.
    op.add_column(
        'products',
        sa.Column(
            'labor_cost',
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
    )

    op.execute(
        "UPDATE products SET labor_cost = 0 "
        "WHERE labor_cost IS NULL"
    )

    op.alter_column(
        'products', 'labor_cost', nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column('products', 'labor_cost')
