"""template emit attempt log

One row per emit_pool_command execution (status, duration, picks, masked
stderr/error text), so a `miss`/`error` can be explained after the fact.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-10-02 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "templateemitattempt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("period_key", sa.String(length=32), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("picked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("picked_refs", sa.String(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["questtemplate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_templateemitattempt_template_id_id",
        "templateemitattempt",
        ["template_id", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_templateemitattempt_template_id_id", table_name="templateemitattempt")
    op.drop_table("templateemitattempt")
