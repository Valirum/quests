"""note color/icon nullable — inherit from parent

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-18 01:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("note", schema=None) as batch_op:
        batch_op.alter_column(
            "color",
            existing_type=sa.String(length=16),
            nullable=True,
            server_default=None,
        )
        batch_op.alter_column(
            "icon",
            existing_type=sa.String(length=32),
            nullable=True,
            server_default=None,
        )
    op.execute(
        """
        UPDATE note SET color = NULL, icon = NULL
        WHERE parent_id IS NOT NULL
          AND custom_icon IS NULL
          AND color IN ('#9a9a9a', '#9A9A9A')
          AND icon = 'document'
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE note SET color = '#9a9a9a' WHERE color IS NULL"
    )
    op.execute(
        "UPDATE note SET icon = 'document' WHERE icon IS NULL"
    )
    with op.batch_alter_table("note", schema=None) as batch_op:
        batch_op.alter_column(
            "icon",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="document",
        )
        batch_op.alter_column(
            "color",
            existing_type=sa.String(length=16),
            nullable=False,
            server_default="#9a9a9a",
        )
