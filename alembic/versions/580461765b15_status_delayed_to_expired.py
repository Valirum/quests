"""status: rename delayed -> expired (quest=216 step=770)

Purely mechanical: the enum string value changes, no behavior change.
The old `delayed` meaning ("overdue", auto-set by ExpireOverdue) becomes
`expired`; a new `delayed` ("отложено", manually set) is introduced by a
later step (quest=216 step=771) and is unrelated to this data.

Revision ID: 580461765b15
Revises: 2aa2bb8ef734
Create Date: 2026-09-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "580461765b15"
down_revision: Union[str, Sequence[str], None] = "2aa2bb8ef734"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE quest SET status = 'expired' WHERE status = 'delayed'")
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE quest SET status = 'delayed' WHERE status = 'expired'")
    )
