"""add quest templates and quest.template_id / period_key

Revision ID: a1b2c3d4e5f6
Revises: 7d093d52e81e
Create Date: 2026-08-02 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "7d093d52e81e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "questtemplate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("freq", sa.String(), nullable=False, server_default="daily"),
        sa.Column("weekdays", sa.String(length=32), nullable=False, server_default="0,1,2,3,4,5,6"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "questtemplatestep",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["questtemplate.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_questtemplatestep_template_id"),
            ["template_id"],
            unique=False,
        )

    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("period_key", sa.String(length=32), nullable=True))
        batch_op.create_index(batch_op.f("ix_quest_template_id"), ["template_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_quest_period_key"), ["period_key"], unique=False)
        batch_op.create_foreign_key(
            "fk_quest_template_id",
            "questtemplate",
            ["template_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_quest_template_period",
            ["template_id", "period_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.drop_constraint("uq_quest_template_period", type_="unique")
        batch_op.drop_constraint("fk_quest_template_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_quest_period_key"))
        batch_op.drop_index(batch_op.f("ix_quest_template_id"))
        batch_op.drop_column("period_key")
        batch_op.drop_column("template_id")

    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_questtemplatestep_template_id"))
    op.drop_table("questtemplatestep")
    op.drop_table("questtemplate")
