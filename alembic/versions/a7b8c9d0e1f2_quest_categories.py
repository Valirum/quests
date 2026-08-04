"""quest categories + category_id on quest/template

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-03 16:25:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED = [
    ("work", "Работа", 10),
    ("routine", "Рутина", 20),
    ("health", "Здоровье", 30),
    ("study", "Учёба", 40),
    ("fun", "Развлечения", 50),
]


def upgrade() -> None:
    op.create_table(
        "questcategory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    with op.batch_alter_table("questcategory", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_questcategory_slug"), ["slug"], unique=False
        )

    for slug, label, sort_order in SEED:
        op.execute(
            sa.text(
                "INSERT INTO questcategory (slug, label, sort_order, created_at) "
                "VALUES (:slug, :label, :sort_order, CURRENT_TIMESTAMP)"
            ).bindparams(slug=slug, label=label, sort_order=sort_order)
        )

    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_quest_category_id"), ["category_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_quest_category_id",
            "questcategory",
            ["category_id"],
            ["id"],
        )

    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_questtemplate_category_id"),
            ["category_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_questtemplate_category_id",
            "questcategory",
            ["category_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.drop_constraint("fk_questtemplate_category_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_questtemplate_category_id"))
        batch_op.drop_column("category_id")
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.drop_constraint("fk_quest_category_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_quest_category_id"))
        batch_op.drop_column("category_id")
    with op.batch_alter_table("questcategory", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_questcategory_slug"))
    op.drop_table("questcategory")
