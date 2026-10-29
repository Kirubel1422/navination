"""Agentic AI: AI-found services, persisted AI plans, bilingual step content, web citations.

Discoveries and journeys created by the earlier rule-based planner cannot be rendered by the
agent-based model, so this migration deletes them (and, by cascade, their steps, messages and
handoffs). Guest sessions and profiles are kept.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("handoffs", "coach_messages", "journey_steps", "journeys", "discoveries"):
        op.execute(sa.text(f"DELETE FROM {table}"))

    op.create_table(
        "ai_services",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["guest_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_services_session_id", "ai_services", ["session_id"])

    with op.batch_alter_table("discoveries") as batch:
        batch.add_column(sa.Column("interpreted_need", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("topic_label", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("notices", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("assessments", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("agent_steps", sa.JSON(), nullable=False, server_default="[]"))

    with op.batch_alter_table("journeys") as batch:
        batch.add_column(sa.Column("plan", sa.JSON(), nullable=False, server_default="{}"))

    with op.batch_alter_table("journey_steps") as batch:
        batch.add_column(sa.Column("key", sa.String(length=64), nullable=False, server_default=""))
        batch.add_column(sa.Column("order_group", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("title", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("instructions", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("checklist", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("assessment", sa.JSON(), nullable=False, server_default="{}"))

    with op.batch_alter_table("coach_messages") as batch:
        batch.add_column(sa.Column("web_citations", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("coach_messages") as batch:
        batch.drop_column("web_citations")
    with op.batch_alter_table("journey_steps") as batch:
        for column in ("assessment", "checklist", "instructions", "title", "order_group", "key"):
            batch.drop_column(column)
    with op.batch_alter_table("journeys") as batch:
        batch.drop_column("plan")
    with op.batch_alter_table("discoveries") as batch:
        for column in ("agent_steps", "assessments", "notices", "topic_label", "interpreted_need"):
            batch.drop_column(column)
    op.drop_index("ix_ai_services_session_id", table_name="ai_services")
    op.drop_table("ai_services")
