"""tags: tag entity + M:N on quest and questtemplate

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-30 21:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#9a9a9a"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    with op.batch_alter_table("tag", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tag_slug"), ["slug"], unique=False)

    op.create_table(
        "quest_tag",
        sa.Column("quest_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["quest_id"], ["quest.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("quest_id", "tag_id"),
    )
    with op.batch_alter_table("quest_tag", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_quest_tag_tag_id"), ["tag_id"], unique=False)

    op.create_table(
        "template_tag",
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["questtemplate.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("template_id", "tag_id"),
    )
    with op.batch_alter_table("template_tag", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_template_tag_tag_id"), ["tag_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("template_tag", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_template_tag_tag_id"))
    op.drop_table("template_tag")
    with op.batch_alter_table("quest_tag", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_quest_tag_tag_id"))
    op.drop_table("quest_tag")
    with op.batch_alter_table("tag", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tag_slug"))
    op.drop_table("tag")
