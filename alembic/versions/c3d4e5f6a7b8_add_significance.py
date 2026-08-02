"""add quest / template significance

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-02 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("significance", sa.String(), nullable=False, server_default="common")
        )
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("significance", sa.String(), nullable=False, server_default="common")
        )


def downgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.drop_column("significance")
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.drop_column("significance")
