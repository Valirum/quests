"""status: rename delayed -> frozen

Purely mechanical: the enum string value changes, no behavior change. The
manual "parked" status was called `delayed`/"отложено", which collided with
the "отложить на N мин" snooze menu; it is now `frozen`/"заморожено".

Revision ID: a9b0c1d2e3f4
Revises: e3f4a5b6c7d8
Create Date: 2026-10-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE quest SET status = 'frozen' WHERE status = 'delayed'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE quest SET status = 'delayed' WHERE status = 'frozen'"))
