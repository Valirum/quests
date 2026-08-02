"""add step check_command / interval / last_run

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-02 16:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("queststep", schema=None) as batch_op:
        batch_op.add_column(sa.Column("check_command", sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column("check_interval_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("check_last_run_at", sa.DateTime(), nullable=True))
    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.add_column(sa.Column("check_command", sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column("check_interval_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.drop_column("check_interval_seconds")
        batch_op.drop_column("check_command")
    with op.batch_alter_table("queststep", schema=None) as batch_op:
        batch_op.drop_column("check_last_run_at")
        batch_op.drop_column("check_interval_seconds")
        batch_op.drop_column("check_command")
