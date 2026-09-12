"""accounts: appuser, usersession, apitoken

Revision ID: a2b3c4d5e6f7
Revises: a1c2e3f4b5d6
Create Date: 2026-09-01 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "a1c2e3f4b5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appuser",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("appuser", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_appuser_username"), ["username"], unique=True)

    op.create_table(
        "usersession",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["user_id"], ["appuser.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("usersession", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_usersession_token_hash"), ["token_hash"], unique=True)
        batch_op.create_index(batch_op.f("ix_usersession_user_id"), ["user_id"], unique=False)

    op.create_table(
        "apitoken",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["appuser.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("apitoken", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_apitoken_token_hash"), ["token_hash"], unique=True)
        batch_op.create_index(batch_op.f("ix_apitoken_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("apitoken", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_apitoken_user_id"))
        batch_op.drop_index(batch_op.f("ix_apitoken_token_hash"))
    op.drop_table("apitoken")
    with op.batch_alter_table("usersession", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_usersession_user_id"))
        batch_op.drop_index(batch_op.f("ix_usersession_token_hash"))
    op.drop_table("usersession")
    with op.batch_alter_table("appuser", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_appuser_username"))
    op.drop_table("appuser")
