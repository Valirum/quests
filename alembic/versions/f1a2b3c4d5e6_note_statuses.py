"""note statuses: is_readme, is_private, is_category

Independent flags (not an enum): README is a personal to-read queue, PRIVATE
hides description from MCP-sourced reads, CATEGORY marks a pure aggregator
note (folder-like, no content of its own). See note=82 for the design.

Revision ID: f1a2b3c4d5e6
Revises: e4f5a6b7c8d9
Create Date: 2026-10-02 18:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("note") as batch_op:
        batch_op.add_column(
            sa.Column("is_readme", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("is_category", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("note") as batch_op:
        batch_op.drop_column("is_category")
        batch_op.drop_column("is_private")
        batch_op.drop_column("is_readme")
