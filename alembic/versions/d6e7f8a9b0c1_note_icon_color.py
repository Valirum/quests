"""note icon, color, custom_icon (like questline)

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-18 01:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("note", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("color", sa.String(length=16), nullable=False, server_default="#9a9a9a")
        )
        batch_op.add_column(
            sa.Column("icon", sa.String(length=32), nullable=False, server_default="document")
        )
        batch_op.add_column(sa.Column("custom_icon", sa.String(length=128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("note", schema=None) as batch_op:
        batch_op.drop_column("custom_icon")
        batch_op.drop_column("icon")
        batch_op.drop_column("color")
