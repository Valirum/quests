"""templatesecret: per-template secrets for emit_pool_command

Revision ID: 2aa2bb8ef734
Revises: b4c5d6e7f8a9
Create Date: 2026-09-27 15:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2aa2bb8ef734"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        # Plaintext — the server itself is the trust boundary (scripts run
        # on the same host), same as the root .env already is. Never
        # returned by any read endpoint or MCP tool regardless; see
        # internal/store/template_secrets.go.
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


def downgrade() -> None:
    op.drop_index("ix_templatesecret_template_key", table_name="templatesecret")
    op.drop_table("templatesecret")
