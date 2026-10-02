"""secret: one table for questline / template / quest / step secrets

Replaces templatesecret. Exactly one owner column is set per row; every owner
FK cascades, so deleting a quest/step/questline/template removes its secrets.
Values are resolved most-specific first (step > quest > template > questline).

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-10-02 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNERS = (
    ("questline_id", "questline"),
    ("template_id", "questtemplate"),
    ("quest_id", "quest"),
    ("step_id", "queststep"),
)


def upgrade() -> None:
    cols = [
        sa.Column(col, sa.Integer(), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), nullable=True)
        for col, table in _OWNERS
    ]
    op.create_table(
        "secret",
        sa.Column("id", sa.Integer(), primary_key=True),
        *cols,
        sa.Column("key", sa.String(length=128), nullable=False),
        # Plaintext: the server is the trust boundary (commands run on the same
        # host, like the root .env). Never returned by a read endpoint or tool.
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(questline_id IS NOT NULL) + (template_id IS NOT NULL)"
            " + (quest_id IS NOT NULL) + (step_id IS NOT NULL) = 1",
            name="ck_secret_one_owner",
        ),
    )
    for col, _ in _OWNERS:
        op.create_index(
            f"ux_secret_{col}_key",
            "secret",
            [col, "key"],
            unique=True,
            sqlite_where=sa.text(f"{col} IS NOT NULL"),
        )
    op.execute(
        "INSERT INTO secret (template_id, key, value, created_at, updated_at) "
        "SELECT template_id, key, value, created_at, updated_at FROM templatesecret"
    )
    op.drop_index("ix_templatesecret_template_key", table_name="templatesecret")
    op.drop_table("templatesecret")


def downgrade() -> None:
    op.create_table(
        "templatesecret",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("questtemplate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_templatesecret_template_key",
        "templatesecret",
        ["template_id", "key"],
        unique=True,
    )
    # Only template-owned secrets have a place in the old schema.
    op.execute(
        "INSERT INTO templatesecret (template_id, key, value, created_at, updated_at) "
        "SELECT template_id, key, value, created_at, updated_at FROM secret "
        "WHERE template_id IS NOT NULL"
    )
    for col, _ in reversed(_OWNERS):
        op.drop_index(f"ux_secret_{col}_key", table_name="secret")
    op.drop_table("secret")
