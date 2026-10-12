"""add applied_at and cycle resource timestamps

Revision ID: 9e529b43dcf3
Revises: 80b468963c2d
Create Date: 2026-10-12 11:02:08.229256

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e529b43dcf3'
down_revision: Union[str, Sequence[str], None] = '80b468963c2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'cycle_resources',
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        'cycle_resources',
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        'production_allocations',
        sa.Column('applied_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('production_allocations', 'applied_at')
    op.drop_column('cycle_resources', 'updated_at')
    op.drop_column('cycle_resources', 'created_at')
