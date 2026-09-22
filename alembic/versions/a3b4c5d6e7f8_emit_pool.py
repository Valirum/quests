"""emit pool: template pool command + roll attempts/picks

Revision ID: a3b4c5d6e7f8
Revises: f8a9b0c1d2e3
Create Date: 2026-09-21 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("emit_pool_command", sa.String(length=2000), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "emit_pool_pick",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )

    with op.batch_alter_table("templateemitroll", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("picked_refs", sa.String(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("templateemitroll", schema=None) as batch_op:
        batch_op.drop_column("picked_refs")
        batch_op.drop_column("attempts")

    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.drop_column("emit_pool_pick")
        batch_op.drop_column("emit_pool_command")
