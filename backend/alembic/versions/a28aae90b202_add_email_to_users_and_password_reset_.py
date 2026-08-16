"""add email to users and password reset tokens

Revision ID: a28aae90b202
Revises: 5a55db5192e6
Create Date: 2026-08-16 21:16:30.652500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a28aae90b202'
down_revision: Union[str, Sequence[str], None] = '5a55db5192e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Added nullable first so existing rows (e.g. the demo admin
    # account) aren't broken by the migration, backfilled with a
    # deterministic placeholder derived from username, then locked to
    # NOT NULL + unique - the standard safe pattern for adding a
    # required column to a table that already has rows.
    op.add_column(
        'users',
        sa.Column('email', sa.String(length=255), nullable=True),
    )

    op.execute(
        "UPDATE users SET email = username || '@armando-furniture.local' "
        "WHERE email IS NULL"
    )

    op.alter_column('users', 'email', nullable=False)

    op.create_index(
        op.f('ix_users_email'), 'users', ['email'], unique=True
    )

    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_password_reset_tokens_id'),
        'password_reset_tokens', ['id'], unique=False,
    )
    op.create_index(
        op.f('ix_password_reset_tokens_user_id'),
        'password_reset_tokens', ['user_id'], unique=False,
    )
    op.create_index(
        op.f('ix_password_reset_tokens_token_hash'),
        'password_reset_tokens', ['token_hash'], unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f('ix_password_reset_tokens_token_hash'),
        table_name='password_reset_tokens',
    )
    op.drop_index(
        op.f('ix_password_reset_tokens_user_id'),
        table_name='password_reset_tokens',
    )
    op.drop_index(
        op.f('ix_password_reset_tokens_id'),
        table_name='password_reset_tokens',
    )
    op.drop_table('password_reset_tokens')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_column('users', 'email')
