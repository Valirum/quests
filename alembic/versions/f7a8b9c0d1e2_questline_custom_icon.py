"""questline.custom_icon for uploaded images

Revision ID: f7a8b9c0d1e2
Revises: e1f2a3b4c5d6
Create Date: 2026-08-09 13:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("questline", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("custom_icon", sa.String(length=64), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("questline", schema=None) as batch_op:
        batch_op.drop_column("custom_icon")
