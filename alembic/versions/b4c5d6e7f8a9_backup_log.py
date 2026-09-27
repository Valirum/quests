"""backuplog: track db backups snapshotted+uploaded for rotation/health

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-27 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backuplog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("webdav_uploaded", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(), nullable=True),
    )
    op.create_index("ix_backuplog_created_at", "backuplog", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_backuplog_created_at", table_name="backuplog")
    op.drop_table("backuplog")
