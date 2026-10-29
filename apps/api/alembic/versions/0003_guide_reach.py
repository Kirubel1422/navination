"""Guide answers and ways to reach a service: the discovery's direct answer, and phone contacts /
nearby centres on coach answers. Additive; existing rows keep working.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("discoveries") as batch:
        batch.add_column(sa.Column("answer", sa.JSON(), nullable=True))
    with op.batch_alter_table("coach_messages") as batch:
        batch.add_column(sa.Column("reach", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("coach_messages") as batch:
        batch.drop_column("reach")
    with op.batch_alter_table("discoveries") as batch:
        batch.drop_column("answer")
