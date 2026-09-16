"""auto steps: wait_previous, run_mode/status; quest.automated

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-16 22:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("queststep", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("wait_previous", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("run_mode", sa.String(length=16), nullable=False, server_default="poll")
        )
        batch_op.add_column(sa.Column("run_status", sa.String(length=16), nullable=True))
    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("wait_previous", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("run_mode", sa.String(length=16), nullable=False, server_default="poll")
        )
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("automated", sa.Integer(), nullable=False, server_default="0")
        )
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("automated", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.drop_column("automated")
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.drop_column("automated")
    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.drop_column("run_mode")
        batch_op.drop_column("wait_previous")
    with op.batch_alter_table("queststep", schema=None) as batch_op:
        batch_op.drop_column("run_status")
        batch_op.drop_column("run_mode")
        batch_op.drop_column("wait_previous")
