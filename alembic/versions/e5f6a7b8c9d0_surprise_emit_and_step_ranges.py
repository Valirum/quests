"""surprise emit fields + template step progress ranges + emit rolls

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-02 19:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "emit_mode",
                sa.String(),
                nullable=False,
                server_default="fixed",
            )
        )
        batch_op.add_column(
            sa.Column(
                "emit_chance",
                sa.Float(),
                nullable=False,
                server_default="1.0",
            )
        )
        batch_op.add_column(
            sa.Column("emit_window_start", sa.String(length=8), nullable=True)
        )
        batch_op.add_column(
            sa.Column("emit_window_end", sa.String(length=8), nullable=True)
        )

    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "progress_min",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.add_column(
            sa.Column(
                "progress_max",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )

    op.execute(
        sa.text(
            "UPDATE questtemplatestep "
            "SET progress_min = progress_total, progress_max = progress_total"
        )
    )

    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.drop_column("progress_total")

    op.create_table(
        "templateemitroll",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("period_key", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["questtemplate.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id", "period_key", name="uq_template_emit_roll_period"
        ),
    )
    with op.batch_alter_table("templateemitroll", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_templateemitroll_template_id"),
            ["template_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_templateemitroll_period_key"),
            ["period_key"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("templateemitroll", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_templateemitroll_period_key"))
        batch_op.drop_index(batch_op.f("ix_templateemitroll_template_id"))
    op.drop_table("templateemitroll")

    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "progress_total",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
    op.execute(
        sa.text(
            "UPDATE questtemplatestep "
            "SET progress_total = progress_max"
        )
    )
    with op.batch_alter_table("questtemplatestep", schema=None) as batch_op:
        batch_op.drop_column("progress_max")
        batch_op.drop_column("progress_min")

    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.drop_column("emit_window_end")
        batch_op.drop_column("emit_window_start")
        batch_op.drop_column("emit_chance")
        batch_op.drop_column("emit_mode")
