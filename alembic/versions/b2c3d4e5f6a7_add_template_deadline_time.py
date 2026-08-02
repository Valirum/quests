"""add questtemplate.deadline_time

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-02 11:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deadline_time", sa.String(length=8), nullable=True))
    # Preserve previous "end of local day" behavior for existing templates.
    op.execute(
        sa.text("UPDATE questtemplate SET deadline_time = '23:59' WHERE deadline_time IS NULL")
    )


def downgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.drop_column("deadline_time")
