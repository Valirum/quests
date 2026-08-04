"""questlines + quest.questline_id

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-03 19:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "questline",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#9a9a9a"),
        sa.Column("icon", sa.String(length=32), nullable=False, server_default="document"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["questcategory.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("questline", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_questline_category_id"), ["category_id"], unique=False
        )

    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.add_column(sa.Column("questline_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_quest_questline_id"), ["questline_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_quest_questline_id",
            "questline",
            ["questline_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.drop_constraint("fk_quest_questline_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_quest_questline_id"))
        batch_op.drop_column("questline_id")
    with op.batch_alter_table("questline", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_questline_category_id"))
    op.drop_table("questline")
