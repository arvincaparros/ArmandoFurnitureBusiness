"""add total cost to optimization runs

Revision ID: 80b468963c2d
Revises: 78b1304118b7
Create Date: 2026-10-09 13:13:22.299077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80b468963c2d'
down_revision: Union[str, Sequence[str], None] = '78b1304118b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Purely additive, nullable column - no backfill. Existing rows
    # keep total_cost = NULL forever (the API/UI already treat that
    # as "unknown", never 0) since there's no historically accurate
    # way to reconstruct a past run's cost from today's prices.
    op.add_column(
        'optimization_runs',
        sa.Column(
            'total_cost',
            sa.Numeric(precision=12, scale=4),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('optimization_runs', 'total_cost')
