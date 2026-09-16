"""attachments: file metadata pointing at WebDAV storage

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-09-16 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "a2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No FK on owner_id: it points at either quest.id or questline.id
    # depending on owner_type, so the constraint can't be expressed here.
    # Orphan rows are cleaned up by the API on owner delete.
    op.create_table(
        "attachment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_type", sa.String(length=16), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("webdav_path", sa.String(length=512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "content_type_declared", sa.String(length=128), nullable=False, server_default=""
        ),
        sa.Column(
            "content_type_detected", sa.String(length=128), nullable=False, server_default=""
        ),
        sa.Column("comment", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("scan_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("scanned_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("attachment", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_attachment_webdav_path"), ["webdav_path"], unique=True
        )
        batch_op.create_index(batch_op.f("ix_attachment_owner_type"), ["owner_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_attachment_owner_id"), ["owner_id"], unique=False)
        # The lookup every listing does.
        batch_op.create_index(
            "ix_attachment_owner", ["owner_type", "owner_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("attachment", schema=None) as batch_op:
        batch_op.drop_index("ix_attachment_owner")
        batch_op.drop_index(batch_op.f("ix_attachment_owner_id"))
        batch_op.drop_index(batch_op.f("ix_attachment_owner_type"))
        batch_op.drop_index(batch_op.f("ix_attachment_webdav_path"))
    op.drop_table("attachment")
