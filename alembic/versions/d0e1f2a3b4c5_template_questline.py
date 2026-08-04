"""questtemplate.questline_id

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-04 11:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("questline_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_questtemplate_questline_id"),
            ["questline_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_questtemplate_questline_id",
            "questline",
            ["questline_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.drop_constraint("fk_questtemplate_questline_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_questtemplate_questline_id"))
        batch_op.drop_column("questline_id")
