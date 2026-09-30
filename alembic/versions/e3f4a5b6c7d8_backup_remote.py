"""backuplog: remote PC upload + attachments archive metadata

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-09-30 23:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("backuplog", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("remote_uploaded", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("attachments_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("attachments_size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("backuplog", schema=None) as batch_op:
        batch_op.drop_column("attachments_size_bytes")
        batch_op.drop_column("attachments_filename")
        batch_op.drop_column("remote_uploaded")
