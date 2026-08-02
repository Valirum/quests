"""initial quest and queststep

Revision ID: df501a4accdb
Revises:
Create Date: 2026-08-02 02:53:53.737543

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "df501a4accdb"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quest",
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "queststep",
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quest_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["quest_id"], ["quest.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("queststep", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_queststep_quest_id"), ["quest_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("queststep", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_queststep_quest_id"))
    op.drop_table("queststep")
    op.drop_table("quest")
