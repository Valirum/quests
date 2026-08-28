"""questchangelog.comment (optional freeform note on a log entry)

Revision ID: a1c2e3f4b5d6
Revises: f7a8b9c0d1e2
Create Date: 2026-08-28 21:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c2e3f4b5d6"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("questchangelog", schema=None) as batch_op:
        batch_op.add_column(sa.Column("comment", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("questchangelog", schema=None) as batch_op:
        batch_op.drop_column("comment")
