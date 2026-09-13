"""add minimum demand to products

Revision ID: fa69029d2755
Revises: b3b943d3e019
Create Date: 2026-09-13 12:24:18.652738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa69029d2755'
down_revision: Union[str, Sequence[str], None] = 'b3b943d3e019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Revision #3 (minimum production demand in the ILP): a per-product
    # floor read directly by optimization.py::create_decision_variables
    # as each decision variable's lowBound - never a positional/array
    # mapping (see the Revision #3 investigation report: Product.id
    # ordering is incidental, not a business contract). Same safe
    # add-nullable/backfill/lock-to-NOT-NULL pattern already used by
    # b3b943d3e019 for products.labor_cost.
    op.add_column(
        'products',
        sa.Column(
            'minimum_demand',
            sa.Numeric(precision=12, scale=4),
            nullable=True,
        ),
    )

    # Finalized values from the thesis `demand` sheet's rounded row
    # (10-week average), matched by product name - name-matching is a
    # one-time backfill concern only; nothing at runtime maps by name
    # or position.
    op.execute(
        "UPDATE products SET minimum_demand = 1 "
        "WHERE name = 'Dining Table (4 seater)'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 1 "
        "WHERE name = 'Dining Table (6 seater)'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 0 "
        "WHERE name = 'Dining Table (8 seater)'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 3 "
        "WHERE name = 'Ordinary Table'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 2 "
        "WHERE name = 'Bed Frame'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 5 "
        "WHERE name = 'Door (60x210)'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 5 "
        "WHERE name = 'Door (70x210)'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 4 "
        "WHERE name = 'Door (80x210)'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 4 "
        "WHERE name = 'Door (90x210)'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 2 "
        "WHERE name = 'High Chair'"
    )
    op.execute(
        "UPDATE products SET minimum_demand = 3 "
        "WHERE name = 'Ordinary Chair'"
    )

    # Any product not named above (none expected today, but future-
    # proof against a product added between writing and running this
    # migration) defaults to no minimum rather than being left NULL.
    op.execute(
        "UPDATE products SET minimum_demand = 0 "
        "WHERE minimum_demand IS NULL"
    )

    op.alter_column(
        'products', 'minimum_demand', nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column('products', 'minimum_demand')
