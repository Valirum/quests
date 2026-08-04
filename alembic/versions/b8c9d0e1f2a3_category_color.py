"""add color to questcategory

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-03 16:35:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLORS = [
    ("work", "#5a8a9a"),
    ("routine", "#8a8578"),
    ("health", "#7a9e3a"),
    ("study", "#6a7ab8"),
    ("fun", "#c47a20"),
]


def upgrade() -> None:
    with op.batch_alter_table("questcategory", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "color",
                sa.String(length=16),
                nullable=False,
                server_default="#9a9a9a",
            )
        )
    for slug, color in COLORS:
        op.execute(
            sa.text(
                "UPDATE questcategory SET color = :color WHERE slug = :slug"
            ).bindparams(slug=slug, color=color)
        )


def downgrade() -> None:
    with op.batch_alter_table("questcategory", schema=None) as batch_op:
        batch_op.drop_column("color")
