"""add production application ledger

Revision ID: 93076b221d5d
Revises: 5f9b8ad6df74
Create Date: 2026-10-30 19:33:37.645495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93076b221d5d'
down_revision: Union[str, Sequence[str], None] = '5f9b8ad6df74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "production_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "application_number", sa.String(length=20), nullable=False,
        ),
        sa.Column("production_cycle_id", sa.Integer(), nullable=False),
        sa.Column("optimization_run_id", sa.Integer(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        # RESTRICT, not CASCADE: this is append-only ledger history
        # and must outlive the cycle/run that produced it - see
        # ProductionApplication.production_cycle_id and
        # .optimization_run_id in app/database/models.py.
        # delete_production_cycle checks for referencing applications
        # and raises a clean 409 before this constraint would ever
        # fire in normal operation.
        sa.ForeignKeyConstraint(
            ["production_cycle_id"],
            ["production_cycles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["optimization_run_id"],
            ["optimization_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "optimization_run_id",
            name="uq_production_application_run",
        ),
    )

    op.create_index(
        op.f("ix_production_applications_id"),
        "production_applications",
        ["id"],
    )

    op.create_index(
        op.f("ix_production_applications_application_number"),
        "production_applications",
        ["application_number"],
        unique=True,
    )

    op.create_index(
        op.f("ix_production_applications_production_cycle_id"),
        "production_applications",
        ["production_cycle_id"],
    )

    op.create_index(
        op.f("ix_production_applications_optimization_run_id"),
        "production_applications",
        ["optimization_run_id"],
    )

    op.create_table(
        "production_application_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "production_application_id", sa.Integer(), nullable=False,
        ),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(
            "quantity_produced", sa.Numeric(12, 4), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["production_application_id"],
            ["production_applications.id"],
            ondelete="CASCADE",
        ),
        # RESTRICT: the production half of available stock must
        # outlive the product record it was produced against - see
        # ProductionApplicationItem.product_id in
        # app/database/models.py.
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "production_application_id",
            "product_id",
            name="uq_production_application_item",
        ),
    )

    op.create_index(
        op.f("ix_production_application_items_id"),
        "production_application_items",
        ["id"],
    )

    op.create_index(
        op.f("ix_production_application_items_production_application_id"),
        "production_application_items",
        ["production_application_id"],
    )

    op.create_index(
        op.f("ix_production_application_items_product_id"),
        "production_application_items",
        ["product_id"],
    )

    op.create_table(
        "production_application_resource_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "production_application_id", sa.Integer(), nullable=False,
        ),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column(
            "resource_name", sa.String(length=100), nullable=False,
        ),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column(
            "consumed_quantity", sa.Numeric(12, 4), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["production_application_id"],
            ["production_applications.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"], ["resources.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "production_application_id",
            "resource_id",
            name="uq_production_application_resource_item",
        ),
    )

    op.create_index(
        op.f("ix_production_application_resource_items_id"),
        "production_application_resource_items",
        ["id"],
    )

    op.create_index(
        op.f(
            "ix_production_application_resource_items_"
            "production_application_id"
        ),
        "production_application_resource_items",
        ["production_application_id"],
    )

    op.create_index(
        op.f("ix_production_application_resource_items_resource_id"),
        "production_application_resource_items",
        ["resource_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("production_application_resource_items")
    op.drop_table("production_application_items")
    op.drop_table("production_applications")
