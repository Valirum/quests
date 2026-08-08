"""quest change log (append-only activity)

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-08 15:25:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "questchangelog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("quest_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=False),
        sa.Column("significance", sa.String(length=16), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["quest_id"], ["quest.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("questchangelog", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_questchangelog_at"), ["at"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_questchangelog_kind"), ["kind"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_questchangelog_quest_id"), ["quest_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_questchangelog_revision"), ["revision"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("questchangelog", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_questchangelog_revision"))
        batch_op.drop_index(batch_op.f("ix_questchangelog_quest_id"))
        batch_op.drop_index(batch_op.f("ix_questchangelog_kind"))
        batch_op.drop_index(batch_op.f("ix_questchangelog_at"))
    op.drop_table("questchangelog")
