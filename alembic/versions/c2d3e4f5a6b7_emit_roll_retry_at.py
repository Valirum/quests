"""templateemitroll.retry_at: pause between emit_pool_command retries

Revision ID: c2d3e4f5a6b7
Revises: b0c1d2e3f4a5
Create Date: 2026-10-02 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("templateemitroll", schema=None) as batch_op:
        batch_op.add_column(sa.Column("retry_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("templateemitroll", schema=None) as batch_op:
        batch_op.drop_column("retry_at")
