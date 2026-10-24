"""add optimization run history flags

Adds the three columns that let an imported, aggregate-only
Optimization History record coexist with native runs:

- products_produced: the imported unit count, shown without needing
  per-product OptimizationResult rows.
- is_history_visible: false would hide a run from Optimization
  History; a caller that must operate on the live plan could still
  read it via /api/optimization/history?include_hidden=true. The
  approved cleanup imports only visible records and native runs are
  always saved visible, so no row is hidden.
- is_summary_only: true for an imported record with no per-product
  rows, which apply_optimization() rejects before deleting anything.

Both booleans are NOT NULL with a server_default so every existing row
keeps today's behavior (visible, applyable) without a backfill UPDATE.

Revision ID: c7a1e4d9f2b8
Revises: 9e529b43dcf3
Create Date: 2026-10-24 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a1e4d9f2b8'
down_revision: Union[str, Sequence[str], None] = '9e529b43dcf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'optimization_runs',
        sa.Column(
            'products_produced',
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        'optimization_runs',
        sa.Column(
            'is_history_visible',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
    )
    op.add_column(
        'optimization_runs',
        sa.Column(
            'is_summary_only',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('optimization_runs', 'is_summary_only')
    op.drop_column('optimization_runs', 'is_history_visible')
    op.drop_column('optimization_runs', 'products_produced')
