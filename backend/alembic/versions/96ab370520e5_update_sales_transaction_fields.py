"""update sales transaction fields

Reconstructed migration. The live database was already stamped at this
revision (alembic_version = '96ab370520e5') and already has this exact
schema, but the migration file itself was never committed to source
control — it was generated/run locally in the same session that added
transaction_number, quantity_produced, and production_cost to the
SalesTransaction model (commit 456f32c), without staging the resulting
alembic/versions file.

This file is reconstructed from:
- direct inspection of the live sales_transactions schema
  (columns, types, nullability, indexes)
- comparison against the prior migration (7fe7eeac7b16), which created
  the table without these columns
- app/database/models.py, app/schemas/transaction.py,
  app/services/transaction.py
- Armando_Furniture_Backend_Final_Implementation_Plan.md section 16
  ("Final Database Changes"), which specifies adding transaction_number,
  quantity_produced, and production_cost

down_revision is set to c9d7150a19d7 (the sole existing head at the time
this change was made) based on circumstantial evidence only: no artifact
in the repository states this revision's parent explicitly. See the
migration-repair audit for details.

unit_price and total_sales are widened from NUMERIC(12,2) to
NUMERIC(12,4) to match the live database exactly. This widening has no
documented origin in the plan, the model, or any commit — it is
undocumented drift being preserved here so a fresh database matches
production, not something the plan or model ever specified.

Revision ID: 96ab370520e5
Revises: c9d7150a19d7
Create Date: 2026-08-12 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96ab370520e5'
down_revision: Union[str, Sequence[str], None] = 'c9d7150a19d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Add new columns as NULLABLE first so this never fails on
    #    NOT NULL violations regardless of existing row count.
    op.add_column(
        'sales_transactions',
        sa.Column('transaction_number', sa.String(length=30), nullable=True),
    )
    op.add_column(
        'sales_transactions',
        sa.Column('quantity_produced', sa.Numeric(precision=12, scale=4), nullable=True),
    )
    op.add_column(
        'sales_transactions',
        sa.Column('production_cost', sa.Numeric(precision=12, scale=4), nullable=True),
    )

    # 2. Widen existing money columns to match the live schema.
    #    Scale 2 -> 4 is a non-lossy widening in PostgreSQL.
    op.alter_column(
        'sales_transactions',
        'unit_price',
        type_=sa.Numeric(precision=12, scale=4),
        existing_type=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
    )
    op.alter_column(
        'sales_transactions',
        'total_sales',
        type_=sa.Numeric(precision=12, scale=4),
        existing_type=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
    )

    # 3. Deterministic backfill for any pre-existing rows.
    #    No-op on an empty table (a fresh database, or the current
    #    production database, which has 0 rows).
    op.execute(
        "UPDATE sales_transactions "
        "SET transaction_number = 'TRX-' || lpad(id::text, 6, '0') "
        "WHERE transaction_number IS NULL"
    )
    op.execute(
        "UPDATE sales_transactions "
        "SET quantity_produced = quantity "
        "WHERE quantity_produced IS NULL"
    )
    op.execute(
        "UPDATE sales_transactions "
        "SET production_cost = 0 "
        "WHERE production_cost IS NULL"
    )

    # 4. Enforce NOT NULL only after backfill guarantees no NULLs remain.
    op.alter_column(
        'sales_transactions',
        'transaction_number',
        nullable=False,
    )
    op.alter_column(
        'sales_transactions',
        'quantity_produced',
        nullable=False,
    )
    op.alter_column(
        'sales_transactions',
        'production_cost',
        nullable=False,
    )

    # 5. Unique index — safe because the id-derived backfill above
    #    guarantees no duplicate transaction_number values.
    op.create_index(
        op.f('ix_sales_transactions_transaction_number'),
        'sales_transactions',
        ['transaction_number'],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_sales_transactions_transaction_number'),
        table_name='sales_transactions',
    )
    op.drop_column('sales_transactions', 'production_cost')
    op.drop_column('sales_transactions', 'quantity_produced')
    op.drop_column('sales_transactions', 'transaction_number')
    op.alter_column(
        'sales_transactions',
        'total_sales',
        type_=sa.Numeric(precision=12, scale=2),
        existing_type=sa.Numeric(precision=12, scale=4),
        existing_nullable=False,
    )
    op.alter_column(
        'sales_transactions',
        'unit_price',
        type_=sa.Numeric(precision=12, scale=2),
        existing_type=sa.Numeric(precision=12, scale=4),
        existing_nullable=False,
    )
