"""note color/icon always owned (copy on create, no inherit)

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-18 01:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Materialize NULL color/icon from nearest ancestor with a value, else defaults.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, parent_id, color, icon FROM note")
    ).fetchall()
    by_id = {r[0]: {"parent_id": r[1], "color": r[2], "icon": r[3]} for r in rows}

    def resolve(nid: int, field: str, default: str) -> str:
        seen = set()
        cur = nid
        while cur is not None and cur not in seen:
            seen.add(cur)
            row = by_id.get(cur)
            if not row:
                return default
            val = row[field]
            if val:
                return val
            cur = row["parent_id"]
        return default

    for nid, row in by_id.items():
        color = row["color"] or resolve(nid, "color", "#9a9a9a")
        icon = row["icon"] or resolve(nid, "icon", "document")
        if row["color"] != color or row["icon"] != icon:
            conn.execute(
                sa.text("UPDATE note SET color = :c, icon = :i WHERE id = :id"),
                {"c": color, "i": icon, "id": nid},
            )

    with op.batch_alter_table("note", schema=None) as batch_op:
        batch_op.alter_column(
            "color",
            existing_type=sa.String(length=16),
            nullable=False,
            server_default="#9a9a9a",
        )
        batch_op.alter_column(
            "icon",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="document",
        )


def downgrade() -> None:
    with op.batch_alter_table("note", schema=None) as batch_op:
        batch_op.alter_column(
            "icon",
            existing_type=sa.String(length=32),
            nullable=True,
            server_default=None,
        )
        batch_op.alter_column(
            "color",
            existing_type=sa.String(length=16),
            nullable=True,
            server_default=None,
        )
