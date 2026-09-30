"""attachment revisions: version history for WebDAV-backed files

Revision ID: c1d2e3f4a5b6
Revises: 580461765b15
Create Date: 2026-09-30 18:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "580461765b15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("attachment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("current_revision", sa.Integer(), nullable=False, server_default="1")
        )

    op.create_table(
        "attachment_revision",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["attachment_id"], ["attachment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attachment_id", "revision", name="uq_attachment_revision"),
        sa.UniqueConstraint("webdav_path", name="uq_attachment_revision_webdav_path"),
    )
    with op.batch_alter_table("attachment_revision", schema=None) as batch_op:
        batch_op.create_index(
            "ix_attachment_revision_attachment_id", ["attachment_id"], unique=False
        )

    # Seed revision 1 from every existing attachment row (current = only version).
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, filename, webdav_path, size_bytes, content_type_declared,
                   content_type_detected, comment, uploaded_at, scan_status, scanned_at
            FROM attachment
            """
        )
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text(
                """
                INSERT INTO attachment_revision (
                    attachment_id, revision, filename, webdav_path, size_bytes,
                    content_type_declared, content_type_detected, comment,
                    uploaded_at, scan_status, scanned_at
                ) VALUES (
                    :aid, 1, :filename, :path, :size,
                    :declared, :detected, :comment,
                    :uploaded, :scan, :scanned
                )
                """
            ),
            {
                "aid": row[0],
                "filename": row[1],
                "path": row[2],
                "size": row[3],
                "declared": row[4],
                "detected": row[5],
                "comment": row[6],
                "uploaded": row[7],
                "scan": row[8],
                "scanned": row[9],
            },
        )


def downgrade() -> None:
    op.drop_table("attachment_revision")
    with op.batch_alter_table("attachment", schema=None) as batch_op:
        batch_op.drop_column("current_revision")
