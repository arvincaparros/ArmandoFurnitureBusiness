"""add confidence and status to forecast results

Revision ID: c4cebd8094aa
Revises: 96ab370520e5
Create Date: 2026-08-15 09:59:38.940112

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4cebd8094aa'
down_revision: Union[str, Sequence[str], None] = '96ab370520e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'forecast_results',
        sa.Column(
            'confidence_level',
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
    )
    op.add_column(
        'forecast_results',
        sa.Column(
            'forecast_status',
            sa.String(length=20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('forecast_results', 'forecast_status')
    op.drop_column('forecast_results', 'confidence_level')
