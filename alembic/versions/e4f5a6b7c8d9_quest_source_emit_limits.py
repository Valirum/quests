"""quest.source (how a quest was created) and questtemplate.emit_limits

source: 'template:<id>' for emitted quests, otherwise the client that created it
(web / cli / mcp / telegram / assistant / api). Old quests get 'template:<id>'
when they have a template, NULL otherwise.
emit_limits: optional JSON overrides of the emit-output size limits.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-10-02 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(length=48), nullable=True))
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.add_column(sa.Column("emit_limits", sa.Text(), nullable=True))
    op.execute(
        "UPDATE quest SET source = 'template:' || template_id WHERE template_id IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("questtemplate", schema=None) as batch_op:
        batch_op.drop_column("emit_limits")
    with op.batch_alter_table("quest", schema=None) as batch_op:
        batch_op.drop_column("source")
